from typing import List, Dict, Optional, Any, Type, Literal, Union
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

class OdooORMSchema(BaseModel):
    operation: Literal[
        'search', 'search_read', 'search_count', 'read', 'create', 
        'write', 'unlink', 'copy', 'default_get', 'name_create',
        'name_search', 'read_group'
    ] = Field(
        description="The ORM operation to perform"
    )
    model: str = Field(
        description="The Odoo model name to operate on (e.g., 'res.partner', 'product.template')"
    )
    # Search parameters
    domain: Optional[List[tuple]] = Field(
        default=None,
        description="""Search domain for filtering records. Examples:
        [('name', '=', 'ABC')] - Exact match
        [('email', 'ilike', 'test@')] - Case-insensitive contains
        ['|', ('phone','ilike','123'), ('mobile','ilike','123')] - OR condition
        [('product_id.qty_available', '<=', 0)] - Related field
        [('birthday.month_number', '=', 2)] - Date parts"""
    )
    fields: Optional[List[str]] = Field(
        default=None,
        description="List of fields to fetch for read/search operations"
    )
    limit: Optional[int] = Field(
        default=None,
        description="Maximum number of records to return"
    )
    offset: Optional[int] = Field(
        default=None,
        description="Number of records to skip"
    )
    order: Optional[str] = Field(
        default=None,
        description="Sort order specification (e.g., 'name ASC, id DESC')"
    )
    # Create/Write/Copy parameters
    values: Optional[Union[Dict[str, Any], List[Dict[str, Any]]]] = Field(
        default=None,
        description="""Values for create/write operations. For create, can be a single dict or list of dicts.
        For write, must be a single dict. Examples:
        {'name': 'Test', 'email': 'test@example.com'}
        [{'name': 'Test 1'}, {'name': 'Test 2'}]"""
    )
    # Read/Write/Unlink/Copy parameters
    ids: Optional[List[int]] = Field(
        default=None,
        description="Record IDs for read/write/unlink/copy operations"
    )
    # Name search parameters
    name: Optional[str] = Field(
        default=None,
        description="Name pattern for name_search operation"
    )
    operator: Optional[str] = Field(
        default='ilike',
        description="Operator for name_search ('like', 'ilike', '=', etc.)"
    )
    # Group by parameters
    groupby: Optional[List[str]] = Field(
        default=None,
        description="""Fields to group by for read_group. Examples:
        ['state'] - Group by state
        ['date:month'] - Group by month
        ['partner_id', 'product_id'] - Multiple grouping"""
    )
    aggregates: Optional[List[str]] = Field(
        default=None,
        description="""Fields to aggregate for read_group. Examples:
        ['amount:sum'] - Sum of amounts
        ['quantity:avg'] - Average of quantities
        ['partner_id:count'] - Count of partners"""
    )
    # Copy parameters
    default: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Default values to override when copying records"
    )

class OdooORMTool(BaseTool):
    """Tool for performing Odoo ORM operations"""
    args_schema: Type[BaseModel] = OdooORMSchema

    def __init__(self, env: Any, name: Optional[str] = None, description: Optional[str] = None, **kwargs: Any) -> None:
        kwargs['name'] = name or "Odoo ORM"
        kwargs['description'] = description or """
    Unified tool for performing Odoo ORM operations on any model.
    
    Examples:
    1. Search: Find active customers
       {
         "operation": "search",
         "model": "res.partner",
         "domain": [("customer_rank", ">", 0), ("active", "=", True)],
         "limit": 10,
         "order": "name ASC"
       }
    
    2. Search and Read: Get customer details
       {
         "operation": "search_read",
         "model": "res.partner",
         "domain": [("customer_rank", ">", 0)],
         "fields": ["name", "email", "phone"],
         "limit": 10
       }

    3. Count Records: Count total customers
       {
         "operation": "search_count",
         "model": "res.partner",
         "domain": [("customer_rank", ">", 0)]
       }
    
    4. Create: Create new products (single or batch)
       Single:
       {
         "operation": "create",
         "model": "product.template",
         "values": {
           "name": "New Product",
           "list_price": 100.0,
           "type": "product"
         }
       }
       Batch:
       {
         "operation": "create",
         "model": "product.template",
         "values": [
           {"name": "Product 1", "list_price": 100.0},
           {"name": "Product 2", "list_price": 200.0}
         ]
       }
    
    5. Write: Update product prices
       {
         "operation": "write",
         "model": "product.template",
         "ids": [1, 2],
         "values": {
           "list_price": 150.0,
           "standard_price": 100.0
         }
       }
    
    6. Copy: Duplicate a sale order
       {
         "operation": "copy",
         "model": "sale.order",
         "ids": [1],
         "default": {
           "date_order": "2024-01-01",
           "name": "New Order"
         }
       }
    
    7. Name Search: Find partners by name
       {
         "operation": "name_search",
         "model": "res.partner",
         "name": "tech",
         "operator": "ilike",
         "domain": [("is_company", "=", True)],
         "limit": 10
       }
    
    8. Read Group: Sales analysis
       {
         "operation": "read_group",
         "model": "sale.order.line",
         "domain": [("state", "=", "sale")],
         "groupby": ["product_id", "order_id"],
         "aggregates": [
           "price_total:sum",
           "product_uom_qty:sum"
         ],
         "limit": 10
       }
    
    9. Unlink: Delete draft quotations
       {
         "operation": "unlink",
         "model": "sale.order",
         "ids": [1, 2, 3]
       }

    Domain Examples:
    - Basic operators: =, !=, >, >=, <, <=
      [("amount", ">", 1000), ("state", "=", "done")]
    
    - String operators: like, ilike, =like, =ilike
      [("name", "ilike", "tech")] - Case insensitive contains
      [("email", "=like", "info_%")] - Case sensitive pattern
    
    - Logical operators: &, |, !
      ["!", ("active", "=", False)] - Not archived
      ["|", ("email", "!=", False), ("phone", "!=", False)] - Has contact
    
    - Relational: Many2one, One2many, Many2many
      [("partner_id.country_id.code", "=", "US")] - Related field
      [("order_line", "any", [("product_id.type", "=", "service")])] - Any line matches
    
    - Date/Time with granularity
      [("create_date.month_number", "=", 1)] - Created in January
      [("date_order.year_number", "=", 2024)] - Orders from 2024
    """
        super().__init__(**kwargs)
        self._env = env

    def _run(
        self,
        operation: str,
        model: str,
        domain: Optional[List[tuple]] = None,
        fields: Optional[List[str]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        order: Optional[str] = None,
        values: Optional[Union[Dict[str, Any], List[Dict[str, Any]]]] = None,
        ids: Optional[List[int]] = None,
        name: Optional[str] = None,
        operator: Optional[str] = 'ilike',
        groupby: Optional[List[str]] = None,
        aggregates: Optional[List[str]] = None,
        default: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        try:
            Model = self._env[model]

            if operation == 'search':
                records = Model.search(
                    domain or [],
                    limit=limit,
                    offset=offset,
                    order=order
                )
                return {
                    'result': 'success',
                    'ids': records.ids,
                    'count': len(records),
                    'message': f'Found {len(records)} records in {model}'
                }

            elif operation == 'search_read':
                records = Model.search_read(
                    domain or [],
                    fields=fields,
                    limit=limit,
                    offset=offset,
                    order=order
                )
                return {
                    'result': 'success',
                    'records': records,
                    'count': len(records),
                    'message': f'Found and read {len(records)} records from {model}'
                }

            elif operation == 'search_count':
                count = Model.search_count(domain or [])
                return {
                    'result': 'success',
                    'count': count,
                    'message': f'Found {count} matching records in {model}'
                }

            elif operation == 'read':
                if not ids:
                    raise ValueError("IDs are required for read operation")
                records = Model.browse(ids).read(fields)
                return {
                    'result': 'success',
                    'records': records,
                    'message': f'Read {len(records)} records from {model}'
                }

            elif operation == 'create':
                if not values:
                    raise ValueError("Values are required for create operation")
                if isinstance(values, list):
                    records = Model.create(values)
                    ids = records.ids
                else:
                    record = Model.create(values)
                    ids = [record.id]
                return {
                    'result': 'success',
                    'ids': ids,
                    'message': f'Created {len(ids)} records in {model}'
                }

            elif operation == 'write':
                if not ids or not values:
                    raise ValueError("Both IDs and values are required for write operation")
                with self._env.cr.savepoint():
                    records = Model.browse(ids)
                    records.write(values)
                    return {
                        'result': 'success',
                        'ids': ids,
                        'message': f'Updated {len(ids)} records in {model}'
                    }

            elif operation == 'copy':
                if not ids:
                    raise ValueError("IDs are required for copy operation")
                records = Model.browse(ids)
                new_records = records.copy(default=default)
                return {
                    'result': 'success',
                    'ids': new_records.ids,
                    'message': f'Copied {len(ids)} records in {model}'
                }

            elif operation == 'name_search':
                if name is None:
                    name = ''
                results = Model.name_search(
                    name=name,
                    args=domain,
                    operator=operator,
                    limit=limit
                )
                return {
                    'result': 'success',
                    'records': results,
                    'count': len(results),
                    'message': f'Found {len(results)} matching names in {model}'
                }

            elif operation == 'read_group':
                if not groupby:
                    raise ValueError("Groupby fields are required for read_group operation")
                groups = Model.read_group(
                    domain=domain or [],
                    fields=aggregates or [],
                    groupby=groupby,
                    offset=offset,
                    limit=limit,
                    orderby=order,
                    lazy=False
                )
                return {
                    'result': 'success',
                    'groups': groups,
                    'count': len(groups),
                    'message': f'Got {len(groups)} groups from {model}'
                }

            elif operation == 'unlink':
                if not ids:
                    raise ValueError("IDs are required for unlink operation")
                records = Model.browse(ids)
                records.unlink()
                return {
                    'result': 'success',
                    'ids': ids,
                    'message': f'Deleted {len(ids)} records from {model}'
                }

            else:
                raise ValueError(f"Invalid operation: {operation}")

        except Exception as e:
            if operation == 'write' and self._env.cr and not self._env.cr.closed:
                self._env.cr.rollback()
            
            error_msg = str(e)
            if 'violates not-null constraint' in error_msg:
                field = error_msg.split('"')[1] if '"' in error_msg else 'unknown'
                error_msg = f"Required field '{field}' is missing"
            
            return {
                'result': 'error',
                'error': error_msg,
                'message': f'Error performing {operation} on {model}: {error_msg}'
            }
