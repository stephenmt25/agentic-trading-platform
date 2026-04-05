from fastapi import FastAPI
from .us_tax import USTaxCalculator
from libs.core.schemas import TaxRequest, TaxEstimateResponse
import uvicorn

app = FastAPI(title="Tax Calculation Service")
    
@app.post("/calculate", response_model=TaxEstimateResponse)
def calculate_tax(req: TaxRequest):
    est = USTaxCalculator.calculate(
        holding_duration_days=req.holding_duration_days,
        net_pnl=req.net_pnl,
        tax_bracket=req.tax_bracket
    )
    return {
        "estimated_tax": est.estimated_tax,
        "effective_rate": est.effective_rate,
        "classification": est.classification
    }

@app.get("/health")
def health():
    return {"status": "healthy"}

if __name__ == "__main__":
    uvicorn.run("services.tax.src.main:app", host="0.0.0.0", port=8089)
