from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.models import Vendor
from app.services.whatsapp import send_text, send_image

async def handle_message(db: Session, phone: str, text: str, chat_id: str, media_url: str = None):
    text = (text or "").strip()

    if not text and not media_url:
        return

    vendor = db.query(Vendor).filter(Vendor.phone == phone).first()
    if not vendor:
        vendor = Vendor(phone=phone, state="new", state_data={})
        db.add(vendor)
        db.commit()
        db.refresh(vendor)

    state = vendor.state

    # Verifica subscrição
    if state == "active":
        if vendor.subscription_end and vendor.subscription_end < datetime.utcnow():
            await send_text(chat_id, (
                "⚠️ *A tua subscrição expirou!*\n\n"
                "Para continuar a usar o KiandaBot, renova o teu plano:\n\n"
                "• Básico — 3.000 Kz/mês\n"
                "• Profissional — 7.500 Kz/mês\n"
                "• Empresarial — 15.000 Kz/mês\n\n"
                "Após o pagamento, envia o comprovativo para o administrador."
            ))
            return

    if state == "new":
        await send_text(chat_id, "👋 Bem-vindo ao *KiandaBot*!\n\nSou o teu assistente de vendas no WhatsApp.\n\nQual é o teu nome?")
        vendor.state = "register_name"
        db.commit()
        return

    if state == "register_name":
        if len(text) < 2:
            await send_text(chat_id, "Por favor envia o teu nome.")
            return
        vendor.name = text.title()
        vendor.state = "register_payment"
        db.commit()
        await send_text(chat_id, f"Olá *{vendor.name}*! 🎉\n\nComo recebes pagamentos?\nEx: _TPA - 923456789_")
        return

    if state == "register_payment":
        if len(text) < 3:
            await send_text(chat_id, "Por favor envia o teu método de pagamento.")
            return
        vendor.state_data = {"payment": text}
        vendor.state = "active"
        vendor.subscription_end = datetime.utcnow() + timedelta(days=30)
        db.commit()
        await send_image(
            chat_id,
            "https://raw.githubusercontent.com/LioExp/imagem-do-delivery-escolar/main/k.jpg",
            "✅ *Registo completo!*\n\nTens *30 dias grátis* para testar o KiandaBot.\n\nDigita *ajuda* para ver os comandos."
        )
        return

    if state == "active":
        cmd = text.lower()

        quer_vender   = any(p in cmd for p in ["quero vender", "vender", "novo produto", "anunciar"])
        quer_saldo    = any(p in cmd for p in ["meu saldo", "saldo", "quanto tenho", "ganhos"])
        quer_ajuda    = any(p in cmd for p in ["ajuda", "menu", "Ajuda", "comandos", "ola", "olá", "oi"])
        quer_produtos = any(p in cmd for p in ["meus produtos", "meus anuncios", "o que vendo", "lista"])
        quer_vendi    = cmd.startswith("vendi ")
        quer_apagar   = any(p in cmd for p in ["apagar produto", "deletar produto", "remover produto"])
        quer_editar   = any(p in cmd for p in ["editar produto", "alterar produto", "modificar produto"])

        if quer_vendi:
            parts = text.split()
            if len(parts) < 3:
                await send_text(chat_id, "Formato incorrecto. Usa:\n*VENDI {codigo} {telefone}*\nEx: VENDI abc12345 244923456789")
                return

            short_code = parts[1].lower()
            buyer_phone = parts[2].replace("+", "").replace(" ", "")

            from app.models import Product, Sale
            product = (
                db.query(Product)
                .filter(Product.short_code == short_code, Product.vendor_id == vendor.id)
                .first()
            )
            if not product:
                await send_text(chat_id, f"Produto *{short_code}* não encontrado. Verifica o código.")
                return

            amount = product.price
            platform_cut = round(amount * 0.05, 2)
            group_cut    = round(amount * 0.05, 2)
            vendor_cut   = round(amount - platform_cut - group_cut, 2)

            sale = Sale(
                product_id=product.id,
                buyer_phone=buyer_phone,
                amount=amount,
                vendor_receives=vendor_cut,
                group_receives=group_cut,
                platform_receives=platform_cut,
            )
            db.add(sale)
            vendor.balance = round(vendor.balance + vendor_cut, 2)
            db.commit()

            await send_text(chat_id, (
                f"✅ *Venda registada!*\n\n"
                f"💰 Valor: *{int(amount):,} Kz*\n"
                f"👤 O teu recebimento: *{int(vendor_cut):,} Kz*\n"
                f"⚙️ Taxa plataforma: {int(platform_cut):,} Kz\n\n"
                f"O teu saldo actual: *{int(vendor.balance):,} Kz*"
            ))
            return

        if quer_apagar:
            from app.models import Product
            products = (
                db.query(Product)
                .filter(Product.vendor_id == vendor.id, Product.status == "active")
                .order_by(Product.created_at.desc())
                .limit(10)
                .all()
            )
            if not products:
                await send_text(chat_id, "Não tens produtos para apagar.")
                return
            lines = ["🗑 *Qual produto queres apagar?*\n\nEnvia o código do produto:\n"]
            for p in products:
                lines.append(f"• *{p.name}* — {int(p.price):,} Kz  |  código: `{p.short_code}`")
            await send_text(chat_id, "\n".join(lines))
            vendor.state = "delete_product"
            db.commit()
            return

        if quer_editar:
            from app.models import Product
            products = (
                db.query(Product)
                .filter(Product.vendor_id == vendor.id, Product.status == "active")
                .order_by(Product.created_at.desc())
                .limit(10)
                .all()
            )
            if not products:
                await send_text(chat_id, "Não tens produtos para editar.")
                return
            lines = ["✏️ *Qual produto queres editar?*\n\nEnvia o código do produto:\n"]
            for p in products:
                lines.append(f"• *{p.name}* — {int(p.price):,} Kz  |  código: `{p.short_code}`")
            await send_text(chat_id, "\n".join(lines))
            vendor.state = "edit_product_select"
            db.commit()
            return

        if quer_vender:
            if media_url:
                descricao = text if len(text) > 5 else None
                if descricao:
                    db.query(Vendor).filter_by(id=vendor.id).update({
                        "state": "add_product_price",
                        "state_data": {"media_url": media_url, "description": descricao}
                    })
                    db.commit()
                    await send_text(chat_id, f"📸 Foto recebida!\n📝 Descrição: _{descricao}_\n\n💰 Qual é o preço em Kz?")
                else:
                    db.query(Vendor).filter_by(id=vendor.id).update({
                        "state": "add_product_description",
                        "state_data": {"media_url": media_url}
                    })
                    db.commit()
                    await send_text(chat_id, "📸 Foto recebida!\n\n📝 Agora envia a descrição do produto.")
            else:
                vendor.state = "add_product_photo"
                db.commit()
                await send_text(chat_id, "🛍 *Novo produto*\n\nEnvia a *foto* do produto.\nSe não tiveres foto, envia um ponto: *.*")
            return

        if quer_saldo:
            await send_text(chat_id, f"💰 O teu saldo: *{int(vendor.balance):,} Kz*")
            return

        if quer_produtos:
            from app.models import Product
            products = (
                db.query(Product)
                .filter(Product.vendor_id == vendor.id, Product.status == "active")
                .order_by(Product.created_at.desc())
                .limit(10)
                .all()
            )
            if not products:
                await send_text(chat_id, "Ainda não tens produtos activos.\n\nEnvia *quero vender* para começar.")
                return
            lines = ["📦 *Os teus produtos:*\n"]
            for p in products:
                lines.append(f"• *{p.name}* — {int(p.price):,} Kz  |  código: `{p.short_code}`")
            await send_text(chat_id, "\n".join(lines))
            return

        if quer_ajuda:
            await send_text(chat_id, (
                "📋 *Comandos disponíveis:*\n\n"
                "🛍 *quero vender* — adicionar produto\n"
                "📦 *meus produtos* — ver os teus produtos\n"
                "✏️ *editar produto* — editar descrição, preço ou foto\n"
                "🗑 *apagar produto* — remover um produto\n"
                "💰 *meu saldo* — ver o teu saldo\n"
                "✅ *VENDI {codigo} {telefone}* — confirmar venda\n"
                "❓ *ajuda* — este menu"
            ))
            return

        await send_text(chat_id, "Não percebi. Digita *ajuda* para ver os comandos.")
        return

    if state == "delete_product":
        if text.lower() == "cancelar":
            vendor.state = "active"
            db.commit()
            await send_text(chat_id, "Operação cancelada.")
            return
        from app.models import Product
        product = (
            db.query(Product)
            .filter(Product.short_code == text.lower(), Product.vendor_id == vendor.id)
            .first()
        )
        if not product:
            await send_text(chat_id, "Código não encontrado. Tenta de novo ou envia *cancelar*.")
            return
        product.status = "deleted"
        vendor.state = "active"
        db.commit()
        await send_text(chat_id, f"🗑 Produto *{product.name}* apagado com sucesso.")
        return

    if state == "edit_product_select":
        if text.lower() == "cancelar":
            vendor.state = "active"
            db.commit()
            await send_text(chat_id, "Operação cancelada.")
            return
        from app.models import Product
        product = (
            db.query(Product)
            .filter(Product.short_code == text.lower(), Product.vendor_id == vendor.id)
            .first()
        )
        if not product:
            await send_text(chat_id, "Código não encontrado. Tenta de novo ou envia *cancelar*.")
            return
        db.query(Vendor).filter_by(id=vendor.id).update({
            "state": "edit_product_field",
            "state_data": {"short_code": product.short_code}
        })
        db.commit()
        await send_text(chat_id, (
            f"✏️ *Editando:* {product.name}\n\n"
            f"O que queres alterar?\n\n"
            f"1 — Descrição\n"
            f"2 — Preço\n"
            f"3 — Foto\n\n"
            f"Responde com 1, 2 ou 3. Ou envia *cancelar*."
        ))
        return

    if state == "edit_product_field":
        if text.lower() == "cancelar":
            vendor.state = "active"
            db.commit()
            await send_text(chat_id, "Operação cancelada.")
            return
        if text.strip() not in ("1", "2", "3"):
            await send_text(chat_id, "Responde com 1, 2 ou 3.")
            return
        data = dict(vendor.state_data or {})
        if text.strip() == "1":
            data["field"] = "description"
        elif text.strip() == "2":
            data["field"] = "price"
        else:
            data["field"] = "photo"
        db.query(Vendor).filter_by(id=vendor.id).update({
            "state": "edit_product_value",
            "state_data": data
        })
        db.commit()
        if data["field"] == "description":
            await send_text(chat_id, "📝 Envia a nova descrição:")
        elif data["field"] == "price":
            await send_text(chat_id, "💰 Envia o novo preço em Kz:")
        else:
            await send_text(chat_id, "📸 Envia a nova foto do produto:")
        return

    if state == "edit_product_value":
        if text.lower() == "cancelar":
            vendor.state = "active"
            db.commit()
            await send_text(chat_id, "Operação cancelada.")
            return
        data = vendor.state_data or {}
        short_code = data.get("short_code")
        field = data.get("field")
        from app.models import Product
        product = (
            db.query(Product)
            .filter(Product.short_code == short_code, Product.vendor_id == vendor.id)
            .first()
        )
        if not product:
            await send_text(chat_id, "Produto não encontrado.")
            vendor.state = "active"
            db.commit()
            return
        if field == "description":
            if len(text) < 3:
                await send_text(chat_id, "Descrição muito curta. Tenta de novo.")
                return
            product.name = " ".join(text.split()[:5])
            product.description = text
            db.commit()
            await send_text(chat_id, f"✅ Descrição actualizada:\n_{text}_")
        elif field == "price":
            try:
                price = float(text.replace(",", "").replace(" ", "").replace("kz", "").lower())
                if price <= 0:
                    raise ValueError()
            except ValueError:
                await send_text(chat_id, "Preço inválido. Envia só o número. Ex: 7500")
                return
            product.price = price
            db.commit()
            await send_text(chat_id, f"✅ Preço actualizado: *{int(price):,} Kz*")
        elif field == "photo":
            if not media_url:
                await send_text(chat_id, "Por favor envia uma foto. Ou envia *cancelar*.")
                return
            product.media_url = media_url
            db.commit()
            await send_text(chat_id, "✅ Foto actualizada com sucesso.")
        vendor.state = "active"
        db.commit()
        return

    if state == "add_product_photo":
        photo_url = media_url if text != "." else None
        db.query(Vendor).filter_by(id=vendor.id).update({
            "state": "add_product_description",
            "state_data": {"media_url": photo_url}
        })
        db.commit()
        await send_text(chat_id, "📝 Agora envia a *descrição* do produto.\nEx: _Vestido africano tamanho M, cor azul_")
        return

    if state == "add_product_description":
        if len(text) < 3:
            await send_text(chat_id, "Descrição muito curta. Tenta de novo.")
            return
        data = dict(vendor.state_data or {})
        data["description"] = text
        db.query(Vendor).filter_by(id=vendor.id).update({
            "state": "add_product_price",
            "state_data": data
        })
        db.commit()
        db.refresh(vendor)
        await send_text(chat_id, "💰 Qual é o *preço* em Kz?\nEnvia só o número. Ex: _7500_")
        return

    if state == "add_product_price":
        try:
            price = float(text.replace(",", "").replace(" ", "").replace("kz", "").lower())
            if price <= 0:
                raise ValueError()
        except ValueError:
            await send_text(chat_id, "Por favor envia só o valor. Ex: _7500_")
            return

        db.refresh(vendor)
        data = vendor.state_data or {}
        description = data.get("description", "")
        media_url_saved = data.get("media_url")

        if not description:
            await send_text(chat_id, "Erro ao recuperar a descrição. Começa de novo enviando *quero vender*.")
            db.query(Vendor).filter_by(id=vendor.id).update({"state": "active", "state_data": {}})
            db.commit()
            return

        import random, string
        short_code = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))

        from app.models import Product, Group
        product = Product(
            vendor_id=vendor.id,
            short_code=short_code,
            name=" ".join(description.split()[:5]),
            description=description,
            price=price,
            media_url=media_url_saved,
            status="active",
        )
        db.add(product)
        db.query(Vendor).filter_by(id=vendor.id).update({"state": "active", "state_data": {}})
        db.commit()
        db.refresh(product)

        from app.services.scheduler import schedule_product
        grupos = db.query(Group).filter(Group.active == True).all()
        group_ids = [g.id for g in grupos]
        if group_ids:
            schedule_product(db, product.id, group_ids)

        from app.config import APP_BASE_URL
        tracking_url = f"{APP_BASE_URL}/p/{short_code}"

        await send_text(chat_id, (
            f"✅ *Produto registado!*\n\n"
            f"📝 {description}\n"
            f"💰 {int(price):,} Kz\n"
            f"🔑 Código: *{short_code}*\n"
            f"🔗 Link: {tracking_url}\n\n"
            f"Quando venderes, envia:\n"
            f"*VENDI {short_code} [telefone do comprador]*"
        ))
        return