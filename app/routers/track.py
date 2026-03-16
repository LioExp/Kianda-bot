import urllib.parse
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Product, Click, Vendor

router = APIRouter(tags=["tracking"])

@router.get("/p/{short_code}")
async def track_and_redirect(
    short_code: str,
    request: Request,
    db: Session = Depends(get_db),
):
    product = db.query(Product).filter(Product.short_code == short_code).first()

    if not product or product.status != "active":
        raise HTTPException(status_code=404, detail="Produto não encontrado.")

    # Regista o clique
    click = Click(product_id=product.id)
    db.add(click)
    db.commit()

    # Carrega o vendedor
    vendor = db.query(Vendor).filter(Vendor.id == product.vendor_id).first()
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendedor não encontrado.")

    phone = vendor.phone.replace("+", "").replace(" ", "")
    if not phone.startswith("244"):
        phone = "244" + phone

    product_name = product.name or product.description[:40] if product.description else "produto"
    text = f"Olá! Vi o produto *{product_name}* e tenho interesse. Ainda está disponível?"
    encoded = urllib.parse.quote(text)
    wa_url = f"https://wa.me/{phone}?text={encoded}"

    return RedirectResponse(url=wa_url, status_code=302)