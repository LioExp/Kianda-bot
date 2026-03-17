import logging
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app.models import Vendor, Product, Group, Sale, Post, Click

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/dashboard", tags=["dashboard"])

# Chave simples de acesso — muda para algo seguro
DASHBOARD_KEY = "kianda2026"


def check_auth(request: Request) -> bool:
    return request.query_params.get("key") == DASHBOARD_KEY


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    if not check_auth(request):
        return HTMLResponse("<h2>Acesso negado. Adiciona ?key=kianda2026 ao URL.</h2>", status_code=401)

    # Estatísticas gerais
    total_vendors = db.query(func.count(Vendor.id)).scalar()
    total_products = db.query(func.count(Product.id)).filter(Product.status == "active").scalar()
    total_sales = db.query(func.count(Sale.id)).scalar()
    total_revenue = db.query(func.sum(Sale.platform_receives)).scalar() or 0
    total_clicks = db.query(func.count(Click.id)).scalar()
    pending_posts = db.query(func.count(Post.id)).filter(Post.status == "pending").scalar()

    # Vendedores
    vendors = db.query(Vendor).order_by(Vendor.created_at.desc()).all()

    # Grupos
    groups = db.query(Group).order_by(Group.created_at.desc()).all()

    # Vendas recentes
    sales = (
        db.query(Sale)
        .order_by(Sale.confirmed_at.desc())
        .limit(20)
        .all()
    )

    # Gera HTML
    vendors_rows = ""
    for v in vendors:
        expiry = v.subscription_end.strftime("%d/%m/%Y") if v.subscription_end else "—"
        expired = v.subscription_end and v.subscription_end < datetime.utcnow()
        estado = "⚠️ Expirado" if expired else "✅ Activo"
        cor = "#fff3cd" if expired else "#d4edda"
        vendors_rows += f"""
        <tr style="background:{cor}">
            <td>{v.name or '—'}</td>
            <td>{v.phone}</td>
            <td>{v.plan}</td>
            <td>{estado}</td>
            <td>{expiry}</td>
            <td>{int(v.balance):,} Kz</td>
        </tr>"""

    groups_rows = ""
    for g in groups:
        estado = "✅" if g.active else "❌"
        groups_rows += f"""
        <tr>
            <td>{estado}</td>
            <td>{g.name}</td>
            <td>{g.owner_phone}</td>
            <td>{int(g.owner_balance):,} Kz</td>
        </tr>"""

    sales_rows = ""
    for s in sales:
        product = db.query(Product).filter(Product.id == s.product_id).first()
        product_name = product.name if product else "—"
        date = s.confirmed_at.strftime("%d/%m %H:%M") if s.confirmed_at else "—"
        sales_rows += f"""
        <tr>
            <td>{date}</td>
            <td>{product_name}</td>
            <td>{s.buyer_phone}</td>
            <td>{int(s.amount):,} Kz</td>
            <td>{int(s.vendor_receives):,} Kz</td>
            <td>{int(s.group_receives):,} Kz</td>
            <td>{int(s.platform_receives):,} Kz</td>
        </tr>"""

    html = f"""
<!DOCTYPE html>
<html lang="pt">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>KiandaBot — Painel</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ font-family: Arial, sans-serif; background: #f5f5f5; color: #333; }}
        .header {{ background: #1B6B3A; color: white; padding: 20px 30px; }}
        .header h1 {{ font-size: 24px; }}
        .header p {{ font-size: 13px; opacity: 0.8; margin-top: 4px; }}
        .container {{ max-width: 1200px; margin: 30px auto; padding: 0 20px; }}
        .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 16px; margin-bottom: 30px; }}
        .card {{ background: white; border-radius: 8px; padding: 20px; text-align: center; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .card .number {{ font-size: 32px; font-weight: bold; color: #1B6B3A; }}
        .card .label {{ font-size: 13px; color: #666; margin-top: 4px; }}
        .section {{ background: white; border-radius: 8px; padding: 20px; margin-bottom: 24px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .section h2 {{ font-size: 16px; margin-bottom: 16px; color: #1B6B3A; border-bottom: 2px solid #1B6B3A; padding-bottom: 8px; }}
        table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
        th {{ background: #1B6B3A; color: white; padding: 10px 12px; text-align: left; }}
        td {{ padding: 9px 12px; border-bottom: 1px solid #eee; }}
        tr:last-child td {{ border-bottom: none; }}
        .updated {{ font-size: 12px; color: #999; text-align: right; margin-top: 20px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🤖 KiandaBot — Painel de Controlo</h1>
        <p>Actualizado em: {datetime.utcnow().strftime("%d/%m/%Y %H:%M")} UTC</p>
    </div>
    <div class="container">
        <div class="cards">
            <div class="card"><div class="number">{total_vendors}</div><div class="label">Vendedores</div></div>
            <div class="card"><div class="number">{total_products}</div><div class="label">Produtos activos</div></div>
            <div class="card"><div class="number">{total_sales}</div><div class="label">Vendas totais</div></div>
            <div class="card"><div class="number">{int(total_revenue):,} Kz</div><div class="label">Receita plataforma</div></div>
            <div class="card"><div class="number">{total_clicks}</div><div class="label">Cliques totais</div></div>
            <div class="card"><div class="number">{pending_posts}</div><div class="label">Posts pendentes</div></div>
        </div>

        <div class="section">
            <h2>👥 Vendedores</h2>
            <table>
                <tr><th>Nome</th><th>Telefone</th><th>Plano</th><th>Estado</th><th>Expira</th><th>Saldo</th></tr>
                {vendors_rows or '<tr><td colspan="6" style="text-align:center;color:#999">Nenhum vendedor</td></tr>'}
            </table>
        </div>

        <div class="section">
            <h2>📢 Grupos</h2>
            <table>
                <tr><th>Estado</th><th>Nome</th><th>Dono</th><th>Saldo</th></tr>
                {groups_rows or '<tr><td colspan="4" style="text-align:center;color:#999">Nenhum grupo</td></tr>'}
            </table>
        </div>

        <div class="section">
            <h2>💰 Vendas recentes</h2>
            <table>
                <tr><th>Data</th><th>Produto</th><th>Comprador</th><th>Total</th><th>Vendedor</th><th>Grupo</th><th>Plataforma</th></tr>
                {sales_rows or '<tr><td colspan="7" style="text-align:center;color:#999">Nenhuma venda</td></tr>'}
            </table>
        </div>

        <p class="updated">KiandaBot v1.0 — <a href="?key=kianda2026">Actualizar</a></p>
    </div>
</body>
</html>"""

    return HTMLResponse(html)