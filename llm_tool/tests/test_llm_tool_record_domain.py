from odoo.tests import tagged

from .common import LLMToolCase


@tagged("post_install", "-at_install")
class TestLLMToolRecordDomain(LLMToolCase):
    """Regression tests for domain validation on the record CRUD tools.

    The domain parameter used to be annotated as
    ``list[list[Union[str, int, bool, float, None]]]``, which pydantic turned
    into a schema that rejected two perfectly valid Odoo domain forms:

    * a list value, required by the ``in`` / ``not in`` operators
    * bare ``&`` / ``|`` / ``!`` logical operator strings

    Sentry SPIN11_PROD-5N: the assistant sent
    ``[["id", "in", [233, 21, 76, 58, 134]]]`` and the call died with
    "4 validation errors for DynamicModel" before ever reaching Odoo.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.retriever = cls.env.ref("llm_tool.llm_tool_odoo_record_retriever")
        cls.updater = cls.env.ref("llm_tool.llm_tool_odoo_record_updater")
        cls.unlinker = cls.env.ref("llm_tool.llm_tool_odoo_record_unlinker")
        cls.partner_a = cls.env["res.partner"].create({"name": "Domain Test A"})
        cls.partner_b = cls.env["res.partner"].create({"name": "Domain Test B"})

    def _validate(self, tool, parameters):
        """Run only the pydantic validation layer of tool.execute()."""
        method = tool._get_implementation_method()
        model = tool.get_pydantic_model_from_signature(method)
        return model(**parameters).model_dump()

    def test_in_operator_domain_passes_validation(self):
        """A list value for the `in` operator must survive validation unchanged"""
        ids = [self.partner_a.id, self.partner_b.id]
        domain = [["id", "in", ids]]

        validated = self._validate(
            self.retriever, {"model": "res.partner", "domain": domain}
        )

        self.assertEqual(validated["domain"], domain)

    def test_logical_operator_domain_passes_validation(self):
        """Bare `|` / `&` / `!` operator strings must survive validation unchanged"""
        domain = [
            "|",
            ["name", "=", "Domain Test A"],
            ["name", "=", "Domain Test B"],
        ]

        validated = self._validate(
            self.retriever, {"model": "res.partner", "domain": domain}
        )

        self.assertEqual(validated["domain"], domain)

    def test_scalar_domain_still_passes_validation(self):
        """The plain [field, op, scalar] form must keep working"""
        domain = [["name", "=", "Domain Test A"]]

        validated = self._validate(
            self.retriever, {"model": "res.partner", "domain": domain}
        )

        self.assertEqual(validated["domain"], domain)

    def test_domain_values_are_not_coerced(self):
        """Booleans / floats / None must not be silently re-typed by pydantic"""
        domain = [
            ["active", "=", True],
            ["parent_id", "=", None],
            ["credit_limit", ">", 10.5],
            ["ref", "=", "123"],
        ]

        validated = self._validate(
            self.retriever, {"model": "res.partner", "domain": domain}
        )

        self.assertEqual(validated["domain"], domain)
        self.assertIs(validated["domain"][0][2], True)
        self.assertIsNone(validated["domain"][1][2])
        self.assertIsInstance(validated["domain"][2][2], float)
        self.assertIsInstance(validated["domain"][3][2], str)

    def test_retriever_executes_in_operator_end_to_end(self):
        """The full execute() path returns the records matched by an `in` domain"""
        ids = [self.partner_a.id, self.partner_b.id]

        result = self.retriever.execute(
            {
                "model": "res.partner",
                "domain": [["id", "in", ids]],
                "fields": ["name"],
            }
        )

        self.assertEqual(sorted(r["id"] for r in result), sorted(ids))
        self.assertEqual(
            sorted(r["name"] for r in result),
            ["Domain Test A", "Domain Test B"],
        )

    def test_updater_accepts_in_operator_domain(self):
        """The updater shares the annotation and must accept list values too"""
        domain = [["id", "in", [self.partner_a.id]]]

        validated = self._validate(
            self.updater,
            {"model": "res.partner", "domain": domain, "values": {"ref": "X1"}},
        )

        self.assertEqual(validated["domain"], domain)

    def test_unlinker_accepts_in_operator_domain(self):
        """The unlinker shares the annotation and must accept list values too"""
        domain = [["id", "in", [self.partner_a.id]]]

        validated = self._validate(
            self.unlinker, {"model": "res.partner", "domain": domain}
        )

        self.assertEqual(validated["domain"], domain)
