from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db import models
from .models import Item
from .utils import get_dynamic_min_stock_level
from io import BytesIO
from openpyxl import Workbook
from django.http import HttpResponse
from Account_management.models import UserLog, Account
import uuid
import json
from django.http import JsonResponse
import os
from django.conf import settings


def _get_existing_inventory_images():
    """Return list of existing images under MEDIA_ROOT/inventory_images as dicts with path and url."""
    images = []
    media_root = getattr(settings, 'MEDIA_ROOT', None)
    media_url = getattr(settings, 'MEDIA_URL', '/media/')
    if not media_root:
        return images

    images_dir = os.path.join(media_root, 'inventory_images')
    if not os.path.isdir(images_dir):
        return images

    for fname in sorted(os.listdir(images_dir)):
        fpath = os.path.join(images_dir, fname)
        if os.path.isfile(fpath):
            images.append({
                'name': fname,
                'path': os.path.join('inventory_images', fname).replace('\\', '/'),
                'url': os.path.join(media_url, 'inventory_images', fname).replace('\\', '/')
            })
    return images


# Main inventory view (list + add)
@login_required
def inventory_view(request):
    products = Item.objects.all().order_by('-id')
    categories = (
        Item.objects.exclude(category__isnull=True)
        .exclude(category__exact='')
        .values_list('category', flat=True)
        .distinct()
    )

    all_items = Item.objects.all()
    low_stock_items_list = []
    for item in all_items:
        dynamic_min_stock = get_dynamic_min_stock_level(item)
        if item.stock < dynamic_min_stock:
            low_stock_items_list.append({
                'name': item.name,
                'stock': item.stock,
                'min_level': dynamic_min_stock
            })

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        sku = request.POST.get('sku', '').strip() or str(uuid.uuid4()).replace('-', '')[:10].upper()
        price = request.POST.get('price', '').strip()
        category_dropdown = request.POST.get('pcategory', '').strip()
        category_input = request.POST.get('category_input', '').strip()
        category = category_input if category_input else category_dropdown or "Uncategorized"
        color_hex = request.POST.get('color_hex', '#ffffff').strip()
        stock = request.POST.get('pstock', '0').strip()
        min_stock_level_form = request.POST.get('min_stock_level', '10').strip()
        image = request.FILES.get('image')
        selected_image = request.POST.get('selected_image')

        if not name or not price:
            messages.error(request, "?? Product name and price are required.")
            return redirect('inventory:list')

        try:
            # If user selected an existing image from server media and did not upload a new file,
            # prefer that selection. The value `selected_image` should be a relative path under MEDIA_ROOT (e.g. 'inventory_images/foo.jpg').
            image_field_value = image
            if not image and selected_image:
                # sanitize path - only allow files under inventory_images/
                if selected_image.startswith('inventory_images/'):
                    image_field_value = selected_image

            item = Item.objects.create(
                name=name,
                sku=sku,
                price=float(price),
                category=category,
                stock=int(stock) if stock.isdigit() else 0,
                min_stock_level=int(min_stock_level_form) if min_stock_level_form.isdigit() else 10,
                color_hex=color_hex,
                image=image_field_value,
            )

            UserLog.objects.create(
                user=request.user,
                action='add',
                description=f"Added product '{item.name}' (SKU: {item.sku})"
            )

            messages.success(request, f"? Product '{item.name}' added successfully.")
            return redirect('inventory:list')

        except Exception as e:
            messages.error(request, f"? Error adding product: {e}")
            print(f"Error adding product: {e}")

    return render(request, 'Inventory/inventory.html', {
        'products': products,
        'categories': categories,
        'low_stock_items': low_stock_items_list,
        'existing_images': _get_existing_inventory_images()
    })


@login_required
def update_product(request, product_id):
    product = get_object_or_404(Item, id=product_id)

    if request.method == 'POST':
        # Basic fields
        product.name = request.POST.get('name', product.name)
        product.category = request.POST.get('category', product.category)
        product.price = request.POST.get('price', product.price)
        product.stock = request.POST.get('stock', product.stock)
        product.min_stock_level = request.POST.get('min_stock_level', product.min_stock_level)

        # Image replacement handling
        # Checkbox 'replace_image' indicates intent to replace/remove current image
        replace_image = request.POST.get('replace_image')
        uploaded_image = request.FILES.get('image')
        selected_image = request.POST.get('selected_image')

        try:
            if replace_image:
                # User intends to replace or remove image
                if uploaded_image:
                    # delete old file if present, then set new image
                    try:
                        if product.image and hasattr(product.image, 'delete'):
                            product.image.delete(save=False)
                    except Exception:
                        pass
                    product.image = uploaded_image
                elif selected_image and selected_image.startswith('inventory_images/'):
                    # User selected an existing server image; validate it exists
                    media_root = getattr(settings, 'MEDIA_ROOT', None)
                    sel_path = os.path.join(media_root or '', selected_image)
                    if media_root and os.path.exists(sel_path):
                        try:
                            if product.image and hasattr(product.image, 'delete'):
                                product.image.delete(save=False)
                        except Exception:
                            pass
                        # Assign relative path to ImageField
                        product.image = selected_image
                    else:
                        # selected image not found; treat as removal
                        try:
                            if product.image and hasattr(product.image, 'delete'):
                                product.image.delete(save=False)
                        except Exception:
                            pass
                        product.image = None
                else:
                    # No uploaded image provided and no selection — remove existing image
                    try:
                        if product.image and hasattr(product.image, 'delete'):
                            product.image.delete(save=False)
                    except Exception:
                        pass
                    product.image = None

            # Save product after processing all fields
            product.save()
        except Exception as e:
            messages.error(request, f"Error updating product image: {e}")
            print(f"Error updating product image: {e}")

        UserLog.objects.create(
            user=request.user,
            action='edit',
            description=f"Edited product '{product.name}' (SKU: {product.sku})"
        )

        messages.success(request, f"✅ Product '{product.name}' updated successfully.")
        return redirect('inventory:list')

    # GET request - show edit form
    categories = (
        Item.objects.exclude(category__isnull=True)
        .exclude(category__exact='')
        .values_list('category', flat=True)
        .distinct()
    )
    
    return render(request, 'Inventory/edit_product.html', {
        'product': product,
        'categories': categories,
        'existing_images': _get_existing_inventory_images()
    })


# Delete product view - ADMIN ONLY + COMPLETE CASCADE DELETE
@login_required
def delete_product(request, product_id):
    product = get_object_or_404(Item, id=product_id)
    
    # ADMIN ONLY - Check if user is superuser/staff
    if not request.user.is_superuser and not request.user.is_staff:
        messages.error(request, "? Only administrators can delete products.")
        return redirect('inventory:list')

    if request.method == 'POST':
        product_name = product.name
        product_sku = product.sku
        product_id_to_delete = product.id

        try:
            from django.db import connection
            
            # Use raw SQL for all deletions to bypass any ORM schema issues
            with connection.cursor() as cursor:
                
                # Step 1: Delete from POS.SaleItem
                try:
                    cursor.execute("DELETE FROM POS_saleitem WHERE product_id = %s", [product_id_to_delete])
                    print(f"? Deleted SaleItems for product {product_id_to_delete}")
                except Exception as e:
                    print(f"SaleItem deletion: {e}")
                
                # Step 2: Delete from Sales_forecast.ForecastResult
                try:
                    cursor.execute("DELETE FROM Sales_forecast_forecastresult WHERE product_id = %s", [product_id_to_delete])
                    print(f"? Deleted ForecastResults for product {product_id_to_delete}")
                except Exception as e:
                    print(f"ForecastResult deletion: {e}")
                
                # Step 3: Delete from Inventory.RestockLog
                try:
                    cursor.execute("DELETE FROM Inventory_restocklog WHERE item_id = %s", [product_id_to_delete])
                    print(f"? Deleted RestockLogs for product {product_id_to_delete}")
                except Exception as e:
                    print(f"RestockLog deletion: {e}")
                
                # Step 4: Delete from Inventory.Item
                try:
                    cursor.execute("DELETE FROM Inventory_item WHERE id = %s", [product_id_to_delete])
                    print(f"? Deleted Item (product) {product_id_to_delete}")
                except Exception as e:
                    print(f"Item deletion error: {e}")
                    raise Exception(f"Failed to delete product: {e}")

            # Log the successful deletion
            UserLog.objects.create(
                user=request.user,
                action='delete',
                description=f"ADMIN DELETE: Product '{product_name}' (SKU: {product_sku}) - All references removed from POS, Sales_forecast, and Inventory"
            )

            messages.success(request, f"? ADMIN DELETED: Product '{product_name}' (SKU: {product_sku}) and all associated records removed from ALL applications.")
            return redirect('inventory:list')

        except Exception as e:
            error_msg = str(e)
            messages.error(request, f"? Deletion failed: {error_msg}")
            print(f"Error during product deletion: {e}")
            import traceback
            traceback.print_exc()
            return redirect('inventory:list')

    # GET request - show confirmation page (ADMIN ONLY)
    return render(request, 'Inventory/delete_confirmation.html', {
        'product': product,
        'related_sales_count': 0,
        'is_admin': request.user.is_superuser or request.user.is_staff
    })


# Restock product view
@login_required
def restock_item(request, product_id):
    product = get_object_or_404(Item, id=product_id)

    if request.method == 'POST':
        # Support JSON/AJAX requests as well as traditional form POSTs.
        is_json = request.headers.get('Content-Type', '').startswith('application/json') or request.headers.get('x-requested-with', '').lower() == 'xmlhttprequest'
        try:
            if is_json:
                try:
                    payload = json.loads(request.body.decode('utf-8') or '{}')
                except Exception:
                    return JsonResponse({'success': False, 'message': 'Invalid JSON payload.'}, status=400)
                restock_amount = int(payload.get('restock_amount', 0))
            else:
                # traditional form submission
                restock_amount = int(request.POST.get('restock_amount', 0))

            if restock_amount <= 0:
                if is_json:
                    return JsonResponse({'success': False, 'message': 'Please enter a valid restock quantity.'}, status=400)
                messages.warning(request, "Please enter a valid restock quantity.")
                return redirect('inventory:list')

            old_stock = product.stock
            product.stock += restock_amount
            product.save()

            UserLog.objects.create(
                user=request.user,
                action='restock',
                description=f"Restocked '{product.name}' (SKU: {product.sku}) from {old_stock} -> {product.stock}"
            )

            if is_json:
                return JsonResponse({'success': True, 'message': f"'{product.name}' restocked by {restock_amount}", 'new_stock': product.stock})

            messages.success(request, f"'{product.name}' restocked by {restock_amount} units (Now: {product.stock}).")
            return redirect('inventory:list')

        except ValueError:
            if is_json:
                return JsonResponse({'success': False, 'message': 'Invalid input. Please enter a number.'}, status=400)
            messages.error(request, "Invalid input. Please enter a number.")
        except Exception as e:
            if is_json:
                return JsonResponse({'success': False, 'message': f'Error during restock: {e}'}, status=500)
            messages.error(request, f"Error during restock: {e}")
            print(f"Error during restock: {e}")

    return redirect('inventory:list')


# Export inventory to Excel
@login_required
def export_inventory_to_excel(request):
    wb = Workbook()
    ws = wb.active
    ws.title = "Inventory Report"

    headers = ['Product Name', 'SKU', 'Price', 'Category', 'Stock Quantity', 'Date Added']
    ws.append(headers)

    items = Item.objects.all().order_by('name')

    for item in items:
        ws.append([
            item.name,
            item.sku,
            float(item.price),
            item.category,
            item.stock,
            item.created_at.strftime('%Y-%m-%d %H:%M:%S')
        ])

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    current_date = timezone.now().strftime('%Y-%m-%d')
    filename = f"inventory_report_{current_date}.xlsx"
    response = HttpResponse(
        buffer.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response
