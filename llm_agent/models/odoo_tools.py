from typing import Any

from pydantic import BaseModel, Field

from crewai.tools import BaseTool


class OdooUserData(BaseModel):
    """Schema for individual user data"""

    name: str = Field(..., description="User's full name")
    login: str = Field(..., description="User's login/username")
    email: str | None = Field(None, description="User's email address")
    company_name: str | None = Field(None, description="Name of user's company")
    active: bool | None = Field(None, description="Whether user is active")

    class Config:
        arbitrary_types_allowed = True


class OdooUsersToolResponse(BaseModel):
    """Schema for tool response"""

    success: bool = Field(..., description="Whether the query was successful")
    message: str = Field(..., description="Status message or error description")
    users: list[OdooUserData] = Field(
        default_factory=list, description="List of matching users"
    )


class OdooQuerySchema(BaseModel):
    """Schema for query generation input."""

    domain: list[tuple] = Field(..., description="Odoo domain for filtering users")
    fields: list[str] | None = Field(
        default=None,
        description="Optional list of specific fields to return. If not provided, returns standard user fields.",
    )


class OdooUsersFetcher(BaseTool):
    """Tool for fetching user data from Odoo using domain filters.

    This tool executes Odoo searches using domain filters and returns user information
    in a structured format.

    Args:
        env: Odoo environment for database operations
        **kwargs: Additional keyword arguments passed to BaseTool
    """

    name: str = "Fetch Odoo Users"
    description: str = """
    A tool for fetching user information from Odoo using domain filters.
    This tool executes the search and returns user data in a structured format.

    Input should be a valid Odoo domain list and optional fields to fetch.
    The tool will return user information matching the domain criteria.

    Domain Structure:
    The domain should be a list of tuples, where each tuple has 3 elements:
    (field_name, operator, value)

    Available operators:
    - '=': Exact match
    - '!=': Not equal
    - '>': Greater than
    - '>=': Greater than or equal
    - '<': Less than
    - '<=': Less than or equal
    - 'like': Case-sensitive pattern match
    - 'ilike': Case-insensitive pattern match
    - 'in': Value must be in list
    - 'not in': Value must not be in list

    Example domains:
    1. Find active users:
       [('active', '=', True)]

    2. Find user by name (case-insensitive):
       [('name', 'ilike', 'John')]

    3. Find internal users from specific company:
       [('share', '=', False), ('company_id', '=', 'My Company')]

    4. Find inactive portal users:
       [('active', '=', False), ('share', '=', True)]

    5. Multiple conditions combined:
       [
           ('active', '=', True),
           ('share', '=', False),
           ('name', 'ilike', 'admin')
       ]

    Available fields:
    - name: User's full name (always included)
    - login: Username/login (always included)
    - email: Email address
    - active: Whether user is active
    - company_id: User's company
    - share: Whether user is portal or internal
    - groups_id: User's security groups
    - partner_id: Related partner record
    - signature: User's signature
    - notification_type: How user receives notifications
    """
    args_schema: type[BaseModel] = OdooQuerySchema
    env: Any = Field(description="Odoo environment")

    def __init__(self, env: Any, **kwargs: Any) -> None:
        """Initialize the OdooUsersFetcher."""
        super().__init__(env=env, **kwargs)
        self._users_model = env["res.users"]

    def _run(
        self,
        domain: list[tuple],
        fields: list[str] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Execute user search with given domain and fields.

        Args:
            domain: Odoo domain for filtering users
            fields: Optional list of fields to return
            **kwargs: Additional keyword arguments

        Returns:
            Dict containing success status, message and list of matching users
        """
        try:
            # Ensure we have the fields we need
            if not fields:
                fields = ["name", "login", "email", "company_id", "active"]
            elif "name" not in fields or "login" not in fields:
                fields.extend(["name", "login"])

            # Process company_id in domain if needed
            domain = self._process_company_domain(domain)

            # Search users with domain
            users = self._users_model.search_read(domain, fields=fields)

            # Convert to response format
            user_data_list = []
            for user in users:
                user_data = {
                    "name": user["name"],
                    "login": user["login"],
                    "email": user.get("email"),
                    "active": user.get("active"),
                }

                if user.get("company_id"):
                    user_data["company_name"] = user["company_id"][1]

                user_data_list.append(OdooUserData(**user_data))

            return OdooUsersToolResponse(
                success=True,
                message=f"Found {len(users)} users matching the criteria.",
                users=user_data_list,
            ).dict()

        except Exception as e:
            return OdooUsersToolResponse(
                success=False, message=f"Error fetching users: {str(e)}", users=[]
            ).dict()

    def _process_company_domain(self, domain: list[tuple]) -> list[tuple]:
        """Process company_id in domain, converting names to IDs if needed."""
        processed_domain = []
        for field, op, value in domain:
            if field == "company_id" and isinstance(value, str):
                # Search for company by name
                company = self.env["res.company"].search(
                    [("name", "ilike", value)], limit=1
                )
                if company:
                    processed_domain.append((field, op, company.id))
                else:
                    # If company not found, keep original to ensure no results
                    processed_domain.append((field, op, -1))
            else:
                processed_domain.append((field, op, value))
        return processed_domain
