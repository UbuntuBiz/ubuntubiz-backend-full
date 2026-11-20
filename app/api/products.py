from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database.connection import get_db
from app.database.models import Product, ProductAlias, StockLevel, User
from app.schemas.inventory import ProductCreate, ProductUpdate, ProductResponse, StockLevelResponse
from app.services.inventory_service import InventoryService
from app.api.deps import get_current_user_and_tenant

router = APIRouter(prefix="/products", tags=["Product Catalog"])


@router.post("", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
def create_product(
    req: ProductCreate,
    current_user: User = Depends(get_current_user_and_tenant),
    db: Session = Depends(get_db)
):
    """
    Add a new product to the spaza shop catalog with optional colloquial township aliases and initial stock.
    """
    # Check for duplicate name in the same shop
    existing = db.query(Product).filter(
        Product.business_id == current_user.business_id,
        Product.name == req.name
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Product with name '{req.name}' already exists in your shop"
        )

    product = Product(
        business_id=current_user.business_id,
        name=req.name,
        unit=req.unit,
        cost_price=req.cost_price,
        sell_price=req.sell_price,
        reorder_point=req.reorder_point,
        expiry_tracked=req.expiry_tracked
    )
    db.add(product)
    db.flush()

    # Add aliases
    for alias_text in req.aliases:
        alias = ProductAlias(
            business_id=current_user.business_id,
            product_id=product.id,
            alias=alias_text.strip().lower()
        )
        db.add(alias)

    # Initialize stock level
    stock = StockLevel(
        business_id=current_user.business_id,
        product_id=product.id,
        qty_on_hand=0
    )
    db.add(stock)
    db.flush()

    # If initial stock provided, record initial stock via event ledger
    if req.initial_stock and req.initial_stock > 0:
        InventoryService.apply_inventory_event(
            db=db,
            business_id=current_user.business_id,
            product_id=product.id,
            event_type="adjustment",
            qty_delta=req.initial_stock,
            reason="Initial stock count on product creation",
            idempotency_key=f"init_stock_{product.id}",
            actor=current_user.id,
            unit_cost=req.cost_price,
            unit_price=req.sell_price
        )

    db.commit()
    db.refresh(product)

    aliases = [a.alias for a in product.aliases]
    qty = product.stock_level.qty_on_hand if product.stock_level else 0
    return ProductResponse(
        id=product.id,
        business_id=product.business_id,
        name=product.name,
        unit=product.unit,
        cost_price=product.cost_price,
        sell_price=product.sell_price,
        reorder_point=product.reorder_point,
        expiry_tracked=product.expiry_tracked,
        created_at=product.created_at,
        qty_on_hand=qty,
        aliases=aliases
    )


@router.get("", response_model=List[ProductResponse])
def list_products(
    search: Optional[str] = None,
    current_user: User = Depends(get_current_user_and_tenant),
    db: Session = Depends(get_db)
):
    """
    List all products in the shop catalog.
    """
    query = db.query(Product).filter(Product.business_id == current_user.business_id)
    if search:
        query = query.filter(Product.name.ilike(f"%{search}%"))

    products = query.all()
    results = []
    for p in products:
        aliases = [a.alias for a in p.aliases]
        qty = p.stock_level.qty_on_hand if p.stock_level else 0
        results.append(ProductResponse(
            id=p.id,
            business_id=p.business_id,
            name=p.name,
            unit=p.unit,
            cost_price=p.cost_price,
            sell_price=p.sell_price,
            reorder_point=p.reorder_point,
            expiry_tracked=p.expiry_tracked,
            created_at=p.created_at,
            qty_on_hand=qty,
            aliases=aliases
        ))
    return results


@router.get("/low-stock", response_model=List[StockLevelResponse])
def get_low_stock_products(
    current_user: User = Depends(get_current_user_and_tenant),
    db: Session = Depends(get_db)
):
    """
    List products whose stock level is at or below their reorder point.
    """
    items = InventoryService.list_low_stock(db, current_user.business_id)
    return items


@router.get("/{product_id}", response_model=ProductResponse)
def get_product(
    product_id: str,
    current_user: User = Depends(get_current_user_and_tenant),
    db: Session = Depends(get_db)
):
    product = db.query(Product).filter(
        Product.id == product_id,
        Product.business_id == current_user.business_id
    ).first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    aliases = [a.alias for a in product.aliases]
    qty = product.stock_level.qty_on_hand if product.stock_level else 0
    return ProductResponse(
        id=product.id,
        business_id=product.business_id,
        name=product.name,
        unit=product.unit,
        cost_price=product.cost_price,
        sell_price=product.sell_price,
        reorder_point=product.reorder_point,
        expiry_tracked=product.expiry_tracked,
        created_at=product.created_at,
        qty_on_hand=qty,
        aliases=aliases
    )


@router.patch("/{product_id}", response_model=ProductResponse)
def update_product(
    product_id: str,
    req: ProductUpdate,
    current_user: User = Depends(get_current_user_and_tenant),
    db: Session = Depends(get_db)
):
    product = db.query(Product).filter(
        Product.id == product_id,
        Product.business_id == current_user.business_id
    ).first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    if req.name is not None:
        product.name = req.name
    if req.unit is not None:
        product.unit = req.unit
    if req.cost_price is not None:
        product.cost_price = req.cost_price
    if req.sell_price is not None:
        product.sell_price = req.sell_price
    if req.reorder_point is not None:
        product.reorder_point = req.reorder_point
    if req.expiry_tracked is not None:
        product.expiry_tracked = req.expiry_tracked

    db.commit()
    db.refresh(product)

    aliases = [a.alias for a in product.aliases]
    qty = product.stock_level.qty_on_hand if product.stock_level else 0
    return ProductResponse(
        id=product.id,
        business_id=product.business_id,
        name=product.name,
        unit=product.unit,
        cost_price=product.cost_price,
        sell_price=product.sell_price,
        reorder_point=product.reorder_point,
        expiry_tracked=product.expiry_tracked,
        created_at=product.created_at,
        qty_on_hand=qty,
        aliases=aliases
    )
