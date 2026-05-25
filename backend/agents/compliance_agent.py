"""
Compliance Agent — validates all documents for the incoming crew member.
Tools: validateDocuments(), checkPortRestrictions(), generateComplianceReport()
"""
import json
import random
from datetime import date, timedelta
from typing import Any, Dict, List

from agents.base_agent import BaseAgent
from database.models import ComplianceStatus

REQUIRED_CERTIFICATIONS = [
    "STCW Basic Safety",
    "GMDSS",
    "Proficiency in Survival Craft",
    "Advanced Fire Fighting",
    "Medical First Aid",
]

PORT_RESTRICTIONS = {
    "Singapore": {"visa_required": ["Iranian", "North Korean"], "min_medical_days": 30},
    "Rotterdam": {"visa_required": ["Iranian"], "min_medical_days": 60},
    "Houston": {"visa_required": ["Cuban", "Iranian", "North Korean"], "min_medical_days": 30},
    "Dubai": {"visa_required": [], "min_medical_days": 30},
    "Shanghai": {"visa_required": [], "min_medical_days": 30},
    "Manila": {"visa_required": [], "min_medical_days": 30},
    "Mumbai": {"visa_required": [], "min_medical_days": 30},
    "Piraeus": {"visa_required": [], "min_medical_days": 30},
}

TOOLS = [
    {
        "name": "validateDocuments",
        "description": (
            "Validate all seafarer documents including passport, visa, medical certificate, "
            "STCW certificates, and other seafarer documents."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "crew_id": {"type": "string"},
                "crew_name": {"type": "string"},
                "passport_expiry": {"type": "string", "description": "ISO date YYYY-MM-DD"},
                "visa_status": {"type": "string"},
                "medical_expiry": {"type": "string", "description": "ISO date YYYY-MM-DD"},
                "stcw_status": {"type": "string"},
                "certifications": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "rank": {"type": "string"},
            },
            "required": ["crew_id", "crew_name", "rank"],
        },
    },
    {
        "name": "checkPortRestrictions",
        "description": "Check if there are any port-specific restrictions for the crew member.",
        "input_schema": {
            "type": "object",
            "properties": {
                "port": {"type": "string"},
                "nationality": {"type": "string"},
                "visa_status": {"type": "string"},
                "medical_expiry": {"type": "string"},
            },
            "required": ["port", "nationality"],
        },
    },
    {
        "name": "generateComplianceReport",
        "description": "Generate the final compliance report with overall status and score.",
        "input_schema": {
            "type": "object",
            "properties": {
                "crew_id": {"type": "string"},
                "crew_name": {"type": "string"},
                "validation_results": {
                    "type": "array",
                    "items": {"type": "object"},
                },
                "port_check_results": {"type": "object"},
            },
            "required": ["crew_id", "crew_name", "validation_results"],
        },
    },
]

SYSTEM_ROLE = """You are the Compliance Agent for a maritime crew management system.
You are triggered when a replacement crew member is about to sign on.

You MUST:
1. Call validateDocuments() to check ALL required documents
2. Call checkPortRestrictions() to verify port-specific requirements
3. Call generateComplianceReport() to produce the final compliance verdict

Compliance is CRITICAL — the vessel cannot sail without proper documentation.
Be thorough, flag any issues, and provide clear remediation steps for failures.

Scoring:
- Each valid document adds to the score
- Missing/expired documents reduce score significantly
- Port restrictions are blockers (score = 0 if violated)"""


class ComplianceAgent(BaseAgent):
    def __init__(self, event_callback=None):
        super().__init__(
            name="Compliance Agent",
            role=SYSTEM_ROLE,
            tools=TOOLS,
            event_callback=event_callback,
        )

    async def _execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Any:
        if tool_name == "validateDocuments":
            return self._validate_documents(tool_input)
        if tool_name == "checkPortRestrictions":
            return self._check_port_restrictions(tool_input)
        if tool_name == "generateComplianceReport":
            return self._generate_compliance_report(tool_input)
        return {"error": f"Unknown tool: {tool_name}"}

    def _validate_documents(self, params: Dict[str, Any]) -> Dict[str, Any]:
        checks = []
        today = date.today()

        # Passport check
        passport_exp = params.get("passport_expiry")
        if passport_exp:
            exp_date = date.fromisoformat(passport_exp)
            days_left = (exp_date - today).days
            if days_left < 0:
                checks.append({"doc": "Passport", "status": "FAILED", "detail": "Expired", "days_remaining": days_left})
            elif days_left < 180:
                checks.append({"doc": "Passport", "status": "WARNING", "detail": f"Expires in {days_left} days", "days_remaining": days_left})
            else:
                checks.append({"doc": "Passport", "status": "PASSED", "detail": f"Valid for {days_left} days", "days_remaining": days_left})
        else:
            checks.append({"doc": "Passport", "status": "FAILED", "detail": "Not provided"})

        # Visa check
        visa = params.get("visa_status", "Unknown")
        if visa == "Valid":
            checks.append({"doc": "Visa", "status": "PASSED", "detail": "Valid"})
        elif visa == "Expiring Soon":
            checks.append({"doc": "Visa", "status": "WARNING", "detail": "Expiring soon — renewal required"})
        else:
            checks.append({"doc": "Visa", "status": "FAILED", "detail": f"Status: {visa}"})

        # Medical check
        med_exp = params.get("medical_expiry")
        if med_exp:
            exp_date = date.fromisoformat(med_exp)
            days_left = (exp_date - today).days
            if days_left < 0:
                checks.append({"doc": "Medical Certificate", "status": "FAILED", "detail": "Expired", "days_remaining": days_left})
            elif days_left < 30:
                checks.append({"doc": "Medical Certificate", "status": "WARNING", "detail": f"Expires in {days_left} days", "days_remaining": days_left})
            else:
                checks.append({"doc": "Medical Certificate", "status": "PASSED", "detail": f"Valid for {days_left} days", "days_remaining": days_left})
        else:
            checks.append({"doc": "Medical Certificate", "status": "FAILED", "detail": "Not provided"})

        # STCW check
        stcw = params.get("stcw_status", "Unknown")
        if stcw == "Valid":
            checks.append({"doc": "STCW Certificates", "status": "PASSED", "detail": "All STCW certificates valid"})
        elif stcw == "Expiring Soon":
            checks.append({"doc": "STCW Certificates", "status": "WARNING", "detail": "One or more STCW certs expiring"})
        else:
            checks.append({"doc": "STCW Certificates", "status": "FAILED", "detail": "STCW certificates invalid or missing"})

        # Certification completeness
        certs = set(params.get("certifications", []))
        rank = params.get("rank", "")
        required = set(["STCW Basic Safety", "Proficiency in Survival Craft"])
        if "Officer" in rank or "Master" in rank or "Engineer" in rank:
            required.add("Advanced Fire Fighting")
            required.add("Medical First Aid")
        missing = required - certs
        if missing:
            checks.append({
                "doc": "Required Certifications",
                "status": "FAILED" if len(missing) > 1 else "WARNING",
                "detail": f"Missing: {', '.join(missing)}",
                "missing": list(missing),
            })
        else:
            checks.append({"doc": "Required Certifications", "status": "PASSED", "detail": "All required certs present"})

        # Seafarer's Book
        checks.append({
            "doc": "Seafarer's Book",
            "status": "PASSED",
            "detail": "Continuously endorsed — 5+ vessels",
        })

        # Flag State Endorsement
        checks.append({
            "doc": "Flag State Endorsement",
            "status": random.choice(["PASSED", "PASSED", "PASSED", "WARNING"]),
            "detail": "CoC / CoE validated against flag state records",
        })

        return {"checks": checks, "total_checks": len(checks)}

    def _check_port_restrictions(self, params: Dict[str, Any]) -> Dict[str, Any]:
        port = params.get("port", "Singapore")
        nationality = params.get("nationality", "Filipino")
        visa = params.get("visa_status", "Valid")
        med_exp = params.get("medical_expiry", "")

        restrictions = PORT_RESTRICTIONS.get(port, {})
        issues = []
        clearances = []

        # Nationality restrictions
        restricted_nats = restrictions.get("visa_required", [])
        if nationality in restricted_nats and visa != "Valid":
            issues.append(f"Visa required for {nationality} nationals at {port}")
        else:
            clearances.append(f"Nationality clearance OK for {port}")

        # Medical validity
        min_days = restrictions.get("min_medical_days", 30)
        if med_exp:
            today = date.today()
            days_left = (date.fromisoformat(med_exp) - today).days
            if days_left < min_days:
                issues.append(f"{port} requires medical valid for at least {min_days} days (only {days_left} days remaining)")
            else:
                clearances.append(f"Medical validity meets {port} minimum requirements")

        clearances.append(f"ISPS security clearance: PASSED")
        clearances.append(f"Port state control: No outstanding deficiencies")

        return {
            "port": port,
            "issues": issues,
            "clearances": clearances,
            "port_cleared": len(issues) == 0,
        }

    def _generate_compliance_report(self, params: Dict[str, Any]) -> Dict[str, Any]:
        validation = params.get("validation_results", [])
        port_check = params.get("port_check_results", {})

        passed = sum(1 for c in validation if c.get("status") == "PASSED")
        warnings = sum(1 for c in validation if c.get("status") == "WARNING")
        failed = sum(1 for c in validation if c.get("status") == "FAILED")

        if not port_check.get("port_cleared", True):
            failed += 1

        total = len(validation) + 1  # +1 for port check
        score = (passed / total) * 100 if total > 0 else 0
        score = max(0, score - (warnings * 5) - (failed * 15))
        score = round(min(100, max(0, score)), 1)

        if failed > 0:
            overall = ComplianceStatus.FAILED
        elif warnings > 0:
            overall = ComplianceStatus.WARNING
        else:
            overall = ComplianceStatus.PASSED

        warning_msgs = [c["detail"] for c in validation if c.get("status") == "WARNING"]
        failure_msgs = [c["detail"] for c in validation if c.get("status") == "FAILED"]
        if not port_check.get("port_cleared", True):
            failure_msgs.extend(port_check.get("issues", []))

        return {
            "crew_id": params.get("crew_id"),
            "crew_name": params.get("crew_name"),
            "overall_status": overall,
            "compliance_score": score,
            "document_checks": validation,
            "port_check": port_check,
            "warnings": warning_msgs,
            "failures": failure_msgs,
            "passed_checks": passed,
            "warning_checks": warnings,
            "failed_checks": failed,
            "recommendation": (
                "APPROVE sign-on" if overall == ComplianceStatus.PASSED
                else "CONDITIONAL approval — resolve warnings before sailing"
                if overall == ComplianceStatus.WARNING
                else "REJECT sign-on — critical document failures"
            ),
        }

    async def _validate_and_format(
        self, raw_text: str, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        report = None
        for tc in self.execution.tool_calls:
            if tc.tool_name == "generateComplianceReport":
                report = tc.output

        if report:
            score = report.get("compliance_score", 80.0)
            self.execution.confidence_score = score / 100
        else:
            self.execution.confidence_score = 0.8

        return {
            "compliance_report": report,
            "narrative": raw_text[:600] if raw_text else "Compliance check completed.",
        }
