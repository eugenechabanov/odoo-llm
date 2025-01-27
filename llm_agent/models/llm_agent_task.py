# models/llm_agent_task.py

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import uuid
import json
import hashlib

class LLMAgentTask(models.Model):
    _name = 'llm.agent.task'
    _description = 'LLM Agent Task'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    # Basic Fields
    name = fields.Char(
        string='Name', 
        required=True, 
        tracking=True,
        translate=True
    )
    description = fields.Text(
        string='Description', 
        required=True, 
        tracking=True,
        translate=True,
        help="Description of the actual task"
    )
    expected_output = fields.Text(
        string='Expected Output', 
        required=True, 
        tracking=True,
        translate=True,
        help="Clear definition of expected output for the task"
    )
    input = fields.Text(
        string='Input', 
        required=True, 
        tracking=True,
        help="Input prompt or request for the LLM agent"
    )
    output = fields.Text(
        string='Output', 
        readonly=True, 
        tracking=True,
        help="Response or output from the LLM agent"
    )
    error = fields.Text(
        string='Error', 
        readonly=True, 
        tracking=True,
        help="Error message if task execution failed"
    )
    
    # Identification and Relations
    task_id = fields.Char(
        string='Task ID', 
        readonly=True, 
        copy=False,
        default=lambda self: str(uuid.uuid4())
    )
    agent_id = fields.Many2one(
        'res.users', 
        string='Assigned Agent', 
        required=True, 
        tracking=True,
        domain=[('is_agent', '=', True)]
    )
    parent_task_id = fields.Many2one(
        'llm.agent.task', 
        string='Parent Task',
        help="Task that delegated this task"
    )
    child_task_ids = fields.One2many(
        'llm.agent.task', 
        'parent_task_id', 
        string='Delegated Tasks'
    )
    context_task_ids = fields.Many2many(
        'llm.agent.task', 
        'llm_agent_task_context_rel', 
        'task_id', 'context_task_id',
        string='Context Tasks',
        help="Other tasks that will have their output used as context for this task"
    )
    
    # Configuration
    config = fields.Json(
        string='Configuration',
        help="Configuration for the task execution"
    )
    allowed_tool_ids = fields.Many2many(
        'llm.agent.tool', 
        string='Allowed Tools',
        help="Tools the agent is limited to use for this task"
    )
    
    # Execution State
    state = fields.Selection([
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('done', 'Done'),
        ('failed', 'Failed')
    ], string='Status', default='pending', tracking=True, required=True)
    is_async = fields.Boolean(
        string='Asynchronous Execution', 
        default=False,
        help="Whether the task should be executed asynchronously"
    )
    
    # Output Management
    output_format = fields.Selection([
        ('raw', 'Raw Text'),
        ('json', 'JSON'),
        ('pydantic', 'Pydantic Model')
    ], string='Output Format', default='raw', required=True)
    output_raw = fields.Text(
        string='Raw Output',
        help="Unprocessed output from the agent",
        tracking=True
    )
    output_json = fields.Json(
        string='JSON Output',
        help="Structured JSON output if format is JSON"
    )
    output_json_schema = fields.Text(
        string='JSON Schema',
        help="JSON schema for structured output"
    )
    output_file = fields.Binary(
        string='Output File', 
        attachment=True
    )
    output_filename = fields.Char(
        string='Output Filename'
    )
    
    # Context and Prompting
    prompt_context = fields.Text(
        string='Prompt Context',
        help="Additional context for task execution"
    )
    conversation_history = fields.Text(
        string='Conversation History',
        help="History of conversation for context"
    )
    require_human_input = fields.Boolean(
        string='Require Human Review', 
        default=False,
        help="Whether the task should have a human review the final answer"
    )
    
    # Guardrail Configuration
    has_guardrail = fields.Boolean(
        string='Has Guardrail',
        help="Whether this task has output validation"
    )
    guardrail_python_code = fields.Text(
        string='Guardrail Code',
        help="Python code for output validation"
    )
    
    # Metrics
    used_tools_count = fields.Integer(string='Tools Used', default=0)
    tool_error_count = fields.Integer(string='Tool Errors', default=0)
    delegation_count = fields.Integer(string='Delegations', default=0)
    retry_count = fields.Integer(string='Retry Count', default=0)
    max_retries = fields.Integer(string='Max Retries', default=3)
    
    # Timing
    start_time = fields.Datetime(string='Start Time')
    end_time = fields.Datetime(string='End Time')
    duration = fields.Float(
        string='Duration (seconds)', 
        compute='_compute_duration'
    )
    
    # Task Key and Original Values
    task_key = fields.Char(
        string='Task Key', 
        compute='_compute_task_key',
        store=True,
        help="MD5 hash of task description and expected output for caching"
    )
    original_description = fields.Text(
        string='Original Description',
        help="Original task description before variable interpolation"
    )
    original_expected_output = fields.Text(
        string='Original Expected Output',
        help="Original expected output before variable interpolation"
    )
    original_output_file = fields.Char(
        string='Original Output File',
        help="Original output file path before variable interpolation"
    )
    
    # Technical Fields
    processed_by_agents = fields.Json(
        string='Processed By Agents', 
        default=dict,
        help="Set of agent IDs that have processed this task"
    )
    user_id = fields.Many2one(
        'res.users', 
        string='Requested By',  
        default=lambda self: self.env.user,
        tracking=True
    )
    message_id = fields.Many2one(
        'mail.message', 
        string='Source Message', 
        readonly=True
    )
    
    @api.depends('start_time', 'end_time')
    def _compute_duration(self):
        for task in self:
            if task.start_time and task.end_time:
                task.duration = (task.end_time - task.start_time).total_seconds()
            else:
                task.duration = 0

    @api.depends('description', 'expected_output')
    def _compute_task_key(self):
        for task in self:
            description = task.original_description or task.description
            expected_output = task.original_expected_output or task.expected_output
            source = f"{description}|{expected_output}"
            task.task_key = hashlib.md5(source.encode()).hexdigest()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name'):
                vals['name'] = _("Task for %s") % self.env['res.users'].browse(vals.get('agent_id')).name
        return super().create(vals_list)

    def action_start(self):
        """Start task execution"""
        self.ensure_one()
        if self.state != 'pending':
            raise ValidationError(_("Only pending tasks can be started"))
            
        self.write({
            'state': 'running',
            'start_time': fields.Datetime.now()
        })
        
        try:
            # Execute the task
            result = self._execute()
            
            # Update task with result
            self.write({
                'state': 'done',
                'end_time': fields.Datetime.now()
            })
            
            return result
        except Exception as e:
            self.write({
                'state': 'failed',
                'error': str(e),
                'end_time': fields.Datetime.now()
            })
            raise

    def action_retry(self):
        """Retry failed task"""
        self.ensure_one()
        if self.state != 'failed':
            raise ValidationError(_("Only failed tasks can be retried"))
        self.write({
            'state': 'pending',
            'error': False,
            'output': False
        })
        return self.action_start()

    def _execute(self):
        """Synchronous task execution"""
        self.ensure_one()
        try:
            if self.has_guardrail:
                return self.execute_with_guardrail()
            else:
                return self._execute_core()
        except Exception as e:
            self._handle_execution_error(e)

    def _execute_core(self):
        """Core task execution logic"""
        self.ensure_one()
        try:
            # Prepare context
            context = self._prepare_context()

            # Execute through agent
            result = self.agent_id._execute_task(
                task=self,
                context=context,
                tools=self.allowed_tool_ids,
            )
            if not result:
                raise ValidationError(_("No output generated from agent"))

            # Store output and update state atomically
            self.write({
                'output': result,
                'output_raw': result,
                'state': 'done',
                'end_time': fields.Datetime.now()
            })
            return result

        except Exception as e:
            raise ValidationError(f"Task execution failed: {str(e)}")

    def _prepare_context(self):
        """Prepare execution context"""
        context = {
            'prompt_context': self.prompt_context,
            'conversation_history': self.conversation_history,
        }
        
        # Add context from related tasks
        if self.context_task_ids:
            context['related_tasks'] = [{
                'description': task.description,
                'output': task.output_raw,
            } for task in self.context_task_ids]
            
        return context

    def _process_output(self, result):
        """Process and store task output"""
        self.ensure_one()
        
        # Store raw output
        self.output_raw = result
        
        # Process based on output format
        if self.output_format == 'json':
            try:
                if isinstance(result, str):
                    self.output_json = json.loads(result)
                else:
                    self.output_json = result
            except json.JSONDecodeError as e:
                raise ValidationError(_("Failed to parse JSON output: %s") % str(e))
                
        # Handle file output if specified
        if self.output_filename:
            # Implementation for file output handling
            pass

    def execute_with_guardrail(self):
        """Execute task with guardrail validation"""
        self.ensure_one()
        
        while self.retry_count < self.max_retries:
            result = self._execute_core()
            
            try:
                # Execute guardrail code
                local_dict = {'task_output': result}
                exec(self.guardrail_python_code, {}, local_dict)
                guardrail_result = local_dict.get('result', (False, "Guardrail check failed"))
                
                success, message = guardrail_result
                if success:
                    return result
                    
                # Log failure and retry
                self.message_post(
                    body=_("Guardrail validation failed: %s. Retrying...") % message
                )
                self.retry_count += 1
                
            except Exception as e:
                self.message_post(
                    body=_("Guardrail code execution failed: %s") % str(e)
                )
                raise
                
        raise ValidationError(_("Task failed guardrail validation after %s retries") % self.max_retries)

    def _handle_execution_error(self, error):
        """Handle task execution errors"""
        self.ensure_one()
        self.message_post(body=_("Task execution failed: %s") % str(error))
        if self.retry_count < self.max_retries:
            self.write({
                'retry_count': self.retry_count + 1,
                'state': 'pending'
            })
        else:
            self.write({'state': 'failed'})

    def delegate_task(self, agent_id, description, expected_output, **kwargs):
        """Create a delegated task"""
        self.ensure_one()
        
        # Increment delegation counter
        self.delegation_count += 1
        
        # Create delegated task
        return self.create({
            'name': f"Delegated: {description[:50]}...",
            'description': description,
            'expected_output': expected_output,
            'agent_id': agent_id,
            'parent_task_id': self.id,
            'state': 'pending',
            **kwargs
        })

    def interpolate_inputs(self, inputs):
        """Interpolate variables in description, expected output, and output file"""
        self.ensure_one()
        
        # Store original values if not already stored
        if not self.original_description:
            self.original_description = self.description
        if not self.original_expected_output:
            self.original_expected_output = self.expected_output
        if not self.original_output_file:
            self.original_output_file = self.output_filename

        # Interpolate values
        self.description = self._interpolate_string(self.original_description, inputs)
        self.expected_output = self._interpolate_string(self.original_expected_output, inputs)
        if self.original_output_file:
            self.output_filename = self._interpolate_string(self.original_output_file, inputs)

    def _interpolate_string(self, input_string, inputs):
        """Interpolate variables in a string while preserving JSON structure"""
        if not input_string:
            return ""
            
        # Check if string contains JSON
        try:
            json_obj = json.loads(input_string)
            return json.dumps(json_obj)  # Return as-is if it's valid JSON
        except json.JSONDecodeError:
            # Not JSON, proceed with normal interpolation
            try:
                return input_string.format(**inputs)
            except KeyError as e:
                raise ValidationError(_("Missing required variable: %s") % str(e))

    def _message_generate_ai_response(self, agent, message, msg_vals):
        """Generate AI response using mail_thread's generate_ai_response.
        
        Args:
            agent (res.users): The AI agent user
            message (mail.message): The message to respond to
            msg_vals (dict): Message values including body
            
        Returns:
            generator: Yields response chunks with content or error
        """
        # Use mail_thread's generate_ai_response
        yield from self.env['mail.thread'].generate_ai_response(agent, message, msg_vals)