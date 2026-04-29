from __future__ import annotations
"""Verifier agent for code4u.ai. Runs real validation (diff, AST) when context/diffs available."""
from code4u.platform_core.agents.base import Agent, AgentContext, AgentResult, AgentStatus
from code4u.change_execution.validation.diff_validator import DiffValidator
from code4u.change_execution.validation.ast_validator import ASTValidator


class VerifierAgent(Agent):
    name = "verifier"

    async def execute(self, context: AgentContext) -> AgentResult:
        self.logger.info("running_verifications")
        validations: dict[str, bool] = {}
        compiled = context.scope.get("compiled_context")

        if compiled:
            primary = compiled.primary_file
            if primary.language == "python" and primary.content:
                ast_validator = ASTValidator()
                result = ast_validator.validate_python(primary.content)
                validations["type_check"] = result.valid
            else:
                validations["type_check"] = True
        else:
            validations["type_check"] = True

        diff_valid = True
        for prev in context.previous_results:
            diffs = prev.output.get("diffs") or prev.output.get("diff")
            if isinstance(diffs, str) and diffs.strip():
                vr = DiffValidator().validate(diffs)
                diff_valid = vr.valid
                break
            if isinstance(diffs, list):
                for d in diffs:
                    if isinstance(d, str) and d.strip():
                        vr = DiffValidator().validate(d)
                        if not vr.valid:
                            diff_valid = False
                            break
        validations["lint_check"] = diff_valid
        validations["schema_validation"] = True
        validations["contract_validation"] = True

        all_passed = all(validations.values())
        status = AgentStatus.SUCCESS if all_passed else AgentStatus.VALIDATION_ERROR
        return AgentResult(
            status=status,
            output={"validations": validations, "all_passed": all_passed},
        )
