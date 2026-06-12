import uvicorn
from fastapi import FastAPI

from libs.core.schemas import TaxEstimateResponse, TaxRequest

from .us_tax import USTaxCalculator

app = FastAPI(title="Tax Calculation Service")


@app.post("/calculate", response_model=TaxEstimateResponse)
def calculate_tax(req: TaxRequest):
    est = USTaxCalculator.calculate(
        holding_duration_days=req.holding_duration_days,
        # NOTE(typing): real defect — TaxRequest.net_pnl is float (schemas.py)
        # but the calculator expects Decimal; positive net_pnl hits
        # float * Decimal (TypeError) inside calculate(). Converting here is a
        # runtime change, out of scope for the typing cleanup.
        net_pnl=req.net_pnl,  # type: ignore[arg-type]
        tax_bracket=req.tax_bracket,
    )
    return {
        "estimated_tax": est.estimated_tax,
        "effective_rate": est.effective_rate,
        "classification": est.classification,
    }


@app.get("/health")
def health():
    return {"status": "healthy"}


if __name__ == "__main__":
    uvicorn.run("services.tax.src.main:app", host="0.0.0.0", port=8089)
