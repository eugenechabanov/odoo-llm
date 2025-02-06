from typing import Any, List, Optional, Type, Dict

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

class OdooUserData(BaseModel):
    """Schema for individual user data"""
    name: str = Field(..., description="User's full name")
    login: str = Field(..., description="User's login/username")
    email: Optional[str] = Field(None, description="User's email address")
    company_name: Optional[str] = Field(None, description="Name of user's company")
    active: Optional[bool] = Field(None, description="Whether user is active")
    
    class Config:
        arbitrary_types_allowed = True


class OdooUsersToolResponse(BaseModel):
    """Schema for tool response"""
    success: bool = Field(..., description="Whether the query was successful")
    message: str = Field(..., description="Status message or error description")
    users: List[OdooUserData] = Field(default_factory=list, description="List of matching users")
    
class OdooUsersToolSchema(BaseModel):
    """Schema for OdooUsersTool input."""
    query: str = Field(..., description="Natural language query to search for users")
    fields: Optional[List[str]] = Field(
        default=None,
        description="Optional list of specific fields to return. If not provided, returns standard user fields."
    )


class OdooUsersTool(BaseTool):
    """Tool for querying Odoo users through natural language.
    
    This tool allows searching for users in Odoo using natural language queries.
    It converts the query into appropriate Odoo domain filters and returns user information.
    
    Args:
        env: Odoo environment for database operations
        **kwargs: Additional keyword arguments passed to BaseTool
    
    Example:
        >>> tool = OdooUsersTool(env=env)
        >>> result = tool.run(query="Find user named John")
    """
    
    name: str = "Query Odoo Users"
    description: str = """
    A tool for searching and retrieving Odoo user information using natural language queries.
    This tool can help you find users based on various criteria and return their information.
    
    You can search users by:
    - Name (e.g., "Find user named John")
    - Email (e.g., "Find user with email john@example.com")
    - Login/username (e.g., "Find user with login admin")
    - Status (e.g., "Find active users")
    - User type (e.g., "Find internal users")
    - Company (e.g., "Find users from Company X")
    
    You can also combine multiple criteria:
    - "Find active internal users from Company X"
    - "Get user John who is active"
    
    The tool will automatically convert your natural language query into proper Odoo domain filters.
    """
    args_schema: Type[BaseModel] = OdooUsersToolSchema
    env: Any = Field(description="Odoo environment")
    
    def __init__(self, env: Any, **kwargs: Any) -> None:
        """Initialize the OdooUsersTool.
        
        Args:
            env: Odoo environment
            **kwargs: Additional keyword arguments passed to BaseTool
        """
        super().__init__(env=env, **kwargs)
        self._users_model = env['res.users']

    def _run(
        self,
        query: str,
        fields: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Execute the tool's main functionality.
        
        Args:
            query: Natural language query to search for users
            fields: Optional list of specific fields to return
            **kwargs: Additional keyword arguments
            
        Returns:
            Dict containing success status, message and list of matching users
        """
        try:
            # Default fields if none specified
            if not fields:
                fields = ['name', 'login', 'email', 'company_id', 'active']

            # Convert natural language query to domain
            domain = self._query_to_domain(query)
            
            # Search users with domain
            users = self._users_model.search_read(domain, fields=fields)
            
            # Convert to response format
            user_data_list = []
            for user in users:
                user_data = {
                    'name': user['name'],
                    'login': user['login'],
                    'email': user.get('email'),
                    'active': user.get('active'),
                }
                
                # Add company name if company_id exists
                if user.get('company_id'):
                    user_data['company_name'] = user['company_id'][1]  # company_id is a tuple (id, name)
                
                user_data_list.append(OdooUserData(**user_data))

            return OdooUsersToolResponse(
                success=True,
                message=f"Found {len(users)} users matching the criteria.",
                users=user_data_list
            ).dict()

        except Exception as e:
            return OdooUsersToolResponse(
                success=False,
                message=f"Error searching users: {str(e)}",
                users=[]
            ).dict()

    def _query_to_domain(self, query: str) -> list:
        """Convert natural language query to Odoo domain"""
        query = query.lower()
        domain = []
        
        # Enhanced query mapping with more patterns
        query_mappings = {
            'active': ('active', '=', True),
            'inactive': ('active', '=', False),
            'internal': ('share', '=', False),
            'portal': ('share', '=', True),
        }
        
        # Add basic mappings
        for key, domain_tuple in query_mappings.items():
            if key in query:
                domain.append(domain_tuple)
        
        # Handle name search
        name_patterns = ['named', 'name is', 'user', 'called']
        for pattern in name_patterns:
            if pattern in query:
                # Try to extract name after the pattern
                parts = query.split(pattern)
                if len(parts) > 1:
                    name = parts[1].strip()
                    # Remove common words that might appear after the name
                    name = name.split(' from ')[0].split(' with ')[0].split(' and ')[0].strip()
                    if name:
                        domain.append(('name', 'ilike', name))
                        break

        # Handle email search
        if 'email' in query:
            parts = query.split('email')
            if len(parts) > 1:
                email = parts[1].strip()
                # Clean up email extraction
                email = email.replace('is', '').replace(':', '').strip()
                if '@' in email:  # Only add if it looks like an email
                    domain.append(('email', 'ilike', email))

        # Handle login search
        if 'login' in query:
            parts = query.split('login')
            if len(parts) > 1:
                login = parts[1].strip()
                # Clean up login extraction
                login = login.replace('is', '').replace(':', '').strip()
                if login:
                    domain.append(('login', 'ilike', login))
        
        # Handle company search
        if 'company' in query:
            companies = self.env['res.company'].search([])
            for company in companies:
                if company.name.lower() in query:
                    domain.append(('company_id', '=', company.id))
                    break
        
        # If no specific domain was created but we have a word that might be a name
        if not domain and len(query.split()) <= 3:  # Assume it's a direct name if query is short
            potential_name = query.replace('find', '').replace('get', '').strip()
            if potential_name:
                domain.append(('name', 'ilike', potential_name))
                
        return domain or []

    def _format_response(self, users: List[Dict[str, Any]]) -> OdooUsersToolResponse:
        """Format user data into a structured response"""
        if not users:
            return OdooUsersToolResponse(
                success=True,
                message="No users found matching the criteria."
            )
            
        user_data_list = []
        for user in users:
            user_data = OdooUserData(
                name=user['name'],
                login=user['login'],
                email=user.get('email'),
                company_name=user['company_id'][1] if user.get('company_id') else None,
                active=user.get('active')
            )
            user_data_list.append(user_data)
            
        return OdooUsersToolResponse(
            success=True,
            message=f"Found {len(users)} users matching the criteria.",
            users=user_data_list
        )
