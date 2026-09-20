"""Redirect-only handoff for products sold by external retailers."""

from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException

from apps.api.models.schemas import RetailerRedirectRequest, RetailerRedirectResponse

router = APIRouter(prefix="/api/retailer", tags=["retailer"])


@router.post("/redirect", response_model=RetailerRedirectResponse)
def retailer_redirect(payload: RetailerRedirectRequest) -> RetailerRedirectResponse:
    parsed = urlparse(payload.product_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HTTPException(status_code=422, detail="product_url must be an HTTP(S) URL")
    return RetailerRedirectResponse(
        product_url=payload.product_url,
        retailer=parsed.netloc,
    )