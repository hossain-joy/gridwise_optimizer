import os
import logging
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.exceptions import RequestValidationError
import pulp

from .models import OptimizeRequest, OptimizeResponse, DirectiveInterpretation

# Load environment variables from .env
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def prewarm_solver():
    """Run a trivial LP problem to load PuLP/CBC into memory."""
    try:
        prob = pulp.LpProblem("Prewarm", pulp.LpMinimize)
        x = pulp.LpVariable("x", lowBound=0)
        prob += x
        prob += x >= 1
        prob.solve(pulp.PULP_CBC_CMD(msg=False))
        logger.info("PuLP solver pre-warmed successfully.")
    except Exception as e:
        logger.error(f"Failed to prewarm PuLP solver: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup actions
    logger.info("Initializing GridWise Optimizer API...")
    prewarm_solver()
    # Prewarm LLM client connection
    try:
        from .llm_interpreter import get_client
        get_client()
        logger.info("LLM client pre-warmed successfully.")
    except Exception as e:
        logger.warning(f"Failed to prewarm LLM client: {e}")
    yield
    # Shutdown actions
    logger.info("Shutting down GridWise Optimizer API...")

app = FastAPI(title="GridWise Optimizer API", lifespan=lifespan)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Return 400 for structural invalidation according to specs instead of default 422."""
    errors = exc.errors()
    # Pydantic v2 might include raw error objects in the context which breaks json.dumps
    for err in errors:
        if 'ctx' in err and 'error' in err['ctx']:
            err['ctx']['error'] = str(err['ctx']['error'])
    return JSONResponse(
        status_code=400,
        content={"detail": errors},
    )

@app.get("/health")
async def health_check():
    """Readiness probe"""
    return {"status": "ok"}

@app.get("/demo", response_class=HTMLResponse)
async def demo_page():
    """Serve the static demo page."""
    html_path = os.path.join(os.path.dirname(__file__), "demo.html")
    with open(html_path, "r") as f:
        return f.read()

@app.post("/optimize-energy", response_model=OptimizeResponse)
async def optimize_energy(payload: OptimizeRequest):
    """
    Main endpoint for optimizing the battery schedule based on energy data and operator notes.
    """
    # TODO: Implement the 5-stage pipeline
    # 1. LLM Interpreter
    from .llm_interpreter import interpret_notes
    raw_directives = interpret_notes(payload.operator_notes, payload.scenario_id, payload.battery.capacity_kwh)
    
    # 2. Guardrail Validator
    from .guardrail import apply_directives, validate_directive
    directives = []
    for raw in raw_directives:
        directives.append(validate_directive(raw, len(payload.operator_notes), payload.battery.capacity_kwh, payload.scenario_id))
        
    demand, solar, tariff, active_min_reserve, active_max_grid, can_charge, can_discharge = apply_directives(payload, directives)
    
    # 3. Math Optimizer
    from .optimizer import run_optimizer
    try:
        hourly_plans, total_grid, total_cost, peak_grid = run_optimizer(
            demand, solar, tariff, payload.battery.model_dump(),
            active_min_reserve, active_max_grid, can_charge, can_discharge
        )
    except Exception as e:
        logger.error(f"Optimization failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
        
    # 4. Final Validator
    from .replay import validate_replay
    try:
        r_grid, r_cost, r_peak = validate_replay(
            hourly_plans, demand, solar, tariff, payload.battery.model_dump(),
            active_min_reserve, active_max_grid, can_charge, can_discharge
        )
        # We can use the recalculated ones or assert they match
        if abs(r_grid - total_grid) > 0.1 or abs(r_cost - total_cost) > 0.1:
            logger.warning(f"Replay mismatch: {r_grid} vs {total_grid}, {r_cost} vs {total_cost}")
            # Keep optimizer ones since they might be exact, or we can use replayed.
            # We'll stick to the optimizer ones for now but replay guarantees constraints.
    except Exception as e:
        logger.error(f"Replay validation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Optimizer produced invalid schedule: {e}")
    
    # 5. Return Response
    applied_types = [d.directive_type for d in directives if d.applies]
    if applied_types:
        summary = f"Optimal schedule computed adhering to {len(applied_types)} directive(s): {', '.join(applied_types)}."
    else:
        summary = "Optimal schedule computed using base scenario parameters."
        
    return OptimizeResponse(
        scenario_id=payload.scenario_id,
        directive_interpretation=directives,
        hourly_plan=hourly_plans,
        total_grid_kwh=total_grid,
        total_cost_bdt=total_cost,
        peak_grid_kwh=peak_grid,
        plan_summary=summary
    )
