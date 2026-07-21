"""Conservative static mail classifier for backup reports.

This parser implements deterministic rules extracted from
PROMPT_AGENTE_CLASIFICACION_BACKUPS.md. It is intentionally conservative: it
identifies known backup-provider signals and proposes a normalized result, but
low-confidence or unknown formats still require manual review.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from apps.backups.models import BackupJob
from apps.ingestion.models import InboundMessage
from apps.parsers.models import ParsedReportItem
from apps.parsers.providers.base import ParsedBackupResult


@dataclass(frozen=True)
class Classification:
    provider: str
    provider_confidence: float
    message_type: str
    parser_status: str
    dashboard_status: str
    confidence: float
    rule_ids: list[str]
    evidence: list[dict[str, str]]
    observation: str
    requires_review: bool
    review_reasons: list[str]
    security_flags: list[str]
    warnings_count: int | None = None
    errors_count: int | None = None
    error_summary: str = ""
    warning_details: str = ""


class StaticMailRulesParser:
    name = "static-mail-rules"
    version = "1"

    def parse(self, message: InboundMessage) -> list[ParsedBackupResult]:
        original_text = self._message_text(message)
        normalized = self._normalize(original_text)
        security_flags = self._security_flags(normalized)
        provider, provider_confidence = self._provider(normalized)
        job_hints = self._job_hints(message=message, normalized_text=normalized)

        classification = self._classify(
            provider=provider,
            provider_confidence=provider_confidence,
            normalized=normalized,
            original_text=original_text,
            security_flags=security_flags,
            job_hints=job_hints,
        )
        return [
            ParsedBackupResult(
                parser_status=classification.parser_status,
                summary=classification.observation,
                occurred_at=message.received_at,
                job_hints=job_hints,
                error_details=classification.error_summary,
                warning_details=classification.warning_details,
                metrics={
                    "provider": classification.provider,
                    "provider_confidence": classification.provider_confidence,
                    "message_type": classification.message_type,
                    "dashboard_status": classification.dashboard_status,
                    "rule_ids": classification.rule_ids,
                    "evidence": classification.evidence,
                    "requires_review": classification.requires_review,
                    "review_reasons": classification.review_reasons,
                    "security_flags": classification.security_flags,
                    "warnings_count": classification.warnings_count,
                    "errors_count": classification.errors_count,
                    "configuration_match": self._configuration_match(job_hints),
                    "parser_prompt": "PROMPT_AGENTE_CLASIFICACION_BACKUPS.md",
                },
                confidence=classification.confidence,
            )
        ]

    def _classify(
        self,
        *,
        provider: str,
        provider_confidence: float,
        normalized: str,
        original_text: str,
        security_flags: list[str],
        job_hints: list[str],
    ) -> Classification:
        if provider == "SCRIPT":
            return self._classify_script(
                normalized=normalized,
                provider_confidence=provider_confidence,
                security_flags=security_flags,
                job_hints=job_hints,
            )
        if provider == "AZURE":
            return self._classify_azure(
                normalized=normalized,
                provider_confidence=provider_confidence,
                security_flags=security_flags,
                job_hints=job_hints,
            )
        if provider == "VEEAM":
            return self._classify_provider_patterns(
                provider="VEEAM",
                provider_confidence=provider_confidence,
                normalized=normalized,
                security_flags=security_flags,
                job_hints=job_hints,
                success_patterns=[
                    r"status\s*[:=]\s*success\b",
                    r"result\s*[:=]\s*success\b",
                    r"session status\s*[:=]\s*success\b",
                    r"job completed successfully",
                    r"backup completed successfully",
                ],
                warning_patterns=[
                    r"status\s*[:=]\s*warning\b",
                    r"result\s*[:=]\s*warning\b",
                    r"session status\s*[:=]\s*warning\b",
                    r"completed with warnings?",
                ],
                failure_patterns=[
                    r"status\s*[:=]\s*fail(?:ed|ure)\b",
                    r"result\s*[:=]\s*fail(?:ed|ure)\b",
                    r"session status\s*[:=]\s*failed\b",
                    r"job failed\b",
                    r"backup failed\b",
                ],
                canceled_patterns=[r"status\s*[:=]\s*(?:canceled|cancelled|stopped)\b"],
                rule_prefix="VEEAM",
            )
        if provider == "IPERIUS":
            return self._classify_provider_patterns(
                provider="IPERIUS",
                provider_confidence=provider_confidence,
                normalized=normalized,
                security_flags=security_flags,
                job_hints=job_hints,
                success_patterns=[
                    r"backup completed successfully",
                    r"backup finished successfully",
                    r"backup completed with success",
                    r"copia finalizada correctamente",
                    r"copia completada correctamente",
                    r"backup terminado correctamente",
                    r"backup completado correctamente",
                    r"backup terminato con successo",
                    r"backup completato con successo",
                    r"backup concluido com sucesso",
                    r"backup completado com sucesso",
                ],
                warning_patterns=[
                    r"completed with warnings?",
                    r"finalizado con advertencias",
                    r"completado con advertencias",
                    r"terminato con avvisi",
                    r"completado com avisos",
                    r"skipped files?\s*[:=]\s*[1-9]\d*",
                ],
                failure_patterns=[
                    r"backup failed\b",
                    r"backup completed with errors?",
                    r"backup finished with errors?",
                    r"copia finalizada con errores",
                    r"backup completado con errores",
                    r"resultado\s*[:=]\s*error\b",
                    r"backup terminato con errori",
                    r"backup completato con errori",
                    r"backup concluido com erros",
                    r"backup completado com erros",
                ],
                canceled_patterns=[],
                rule_prefix="IPERIUS",
            )
        if provider in {"NAKIVO", "QNAP_HBS", "CUBEBACKUP"}:
            return self._classify_provider_patterns(
                provider=provider,
                provider_confidence=provider_confidence,
                normalized=normalized,
                security_flags=security_flags,
                job_hints=job_hints,
                success_patterns=[r"status\s*[:=]\s*success(?:ful)?\b", r"completed successfully"],
                warning_patterns=[r"completed with warnings?", r"finished with errors?"],
                failure_patterns=[r"status\s*[:=]\s*failed\b", r"job failed\b", r"backup failed\b"],
                canceled_patterns=[r"status\s*[:=]\s*(?:canceled|cancelled|stopped)\b"],
                rule_prefix=provider,
            )
        if provider == "AWS_DLM":
            return self._classify_aws_dlm(
                normalized=normalized,
                provider_confidence=provider_confidence,
                security_flags=security_flags,
                job_hints=job_hints,
            )
        return self._unknown(
            provider=provider,
            provider_confidence=provider_confidence,
            message_type="UNKNOWN_MESSAGE",
            rule_ids=["UNKNOWN_TEMPLATE"],
            security_flags=security_flags,
            review_reasons=["UNKNOWN_PROVIDER"],
        )

    def _classify_provider_patterns(
        self,
        *,
        provider: str,
        provider_confidence: float,
        normalized: str,
        security_flags: list[str],
        job_hints: list[str],
        success_patterns: list[str],
        warning_patterns: list[str],
        failure_patterns: list[str],
        canceled_patterns: list[str],
        rule_prefix: str,
    ) -> Classification:
        warnings_count = self._counter(normalized, "warnings?")
        errors_count = self._counter(normalized, "errors?|failed|failures?")
        evidence: list[dict[str, str]] = []

        canceled = self._first_match(normalized, canceled_patterns)
        failure = self._first_match(normalized, failure_patterns)
        warning = self._first_match(normalized, warning_patterns)
        success = self._first_match(normalized, success_patterns)

        if success and (errors_count or 0) > 0:
            return self._unknown(
                provider=provider,
                provider_confidence=provider_confidence,
                message_type="BACKUP_REPORT",
                rule_ids=[f"{rule_prefix}_CONTRADICTORY_RESULT"],
                security_flags=security_flags,
                review_reasons=["SUCCESS_WITH_NONZERO_ERRORS", "CONFLICTING_FINAL_STATUS"],
                warnings_count=warnings_count,
                errors_count=errors_count,
            )
        if canceled:
            evidence.append(self._evidence(canceled.group(0), "CANCELED"))
            return self._classification(
                provider=provider,
                provider_confidence=provider_confidence,
                message_type="BACKUP_REPORT",
                parser_status=ParsedReportItem.ParserStatus.CANCELED,
                dashboard_status="ERROR",
                confidence=0.9,
                rule_ids=[f"{rule_prefix}_CANCELED_OR_STOPPED"],
                evidence=evidence,
                observation="La tarea fue cancelada o detenida y requiere revisión.",
                requires_review=True,
                review_reasons=["CANCELED_REQUIRES_CONFIRMATION"],
                security_flags=security_flags,
                warnings_count=warnings_count,
                errors_count=errors_count,
                error_summary="La tarea fue cancelada o detenida.",
            )
        if failure or (errors_count or 0) > 0:
            text = failure.group(0) if failure else f"errors: {errors_count}"
            evidence.append(self._evidence(text, "FAILED"))
            return self._classification(
                provider=provider,
                provider_confidence=provider_confidence,
                message_type="BACKUP_REPORT",
                parser_status=ParsedReportItem.ParserStatus.FAILED,
                dashboard_status="ERROR",
                confidence=self._confidence(0.92, provider_confidence, job_hints),
                rule_ids=[f"{rule_prefix}_FAILURE_EXPLICIT"],
                evidence=evidence,
                observation="La tarea falló según el reporte.",
                requires_review=self._requires_review(0.92, provider_confidence, job_hints),
                review_reasons=self._review_reasons(0.92, provider_confidence, job_hints),
                security_flags=security_flags,
                warnings_count=warnings_count,
                errors_count=errors_count,
                error_summary="La tarea falló según el reporte.",
            )
        if warning or (warnings_count or 0) > 0:
            text = warning.group(0) if warning else f"warnings: {warnings_count}"
            evidence.append(self._evidence(text, "WARNING"))
            return self._classification(
                provider=provider,
                provider_confidence=provider_confidence,
                message_type="BACKUP_REPORT",
                parser_status=ParsedReportItem.ParserStatus.WARNING,
                dashboard_status="WARNING",
                confidence=self._confidence(0.92, provider_confidence, job_hints),
                rule_ids=[f"{rule_prefix}_WARNING_EXPLICIT"],
                evidence=evidence,
                observation="La tarea finalizó con advertencias.",
                requires_review=self._requires_review(0.92, provider_confidence, job_hints),
                review_reasons=self._review_reasons(0.92, provider_confidence, job_hints),
                security_flags=security_flags,
                warnings_count=warnings_count,
                errors_count=errors_count,
                warning_details="La tarea finalizó con advertencias.",
            )
        if success:
            evidence.append(self._evidence(success.group(0), "SUCCESS"))
            return self._classification(
                provider=provider,
                provider_confidence=provider_confidence,
                message_type="BACKUP_REPORT",
                parser_status=ParsedReportItem.ParserStatus.SUCCESS,
                dashboard_status="CORRECTO",
                confidence=self._confidence(0.98, provider_confidence, job_hints),
                rule_ids=[f"{rule_prefix}_SUCCESS_EXPLICIT"],
                evidence=evidence,
                observation="La tarea finalizó correctamente.",
                requires_review=self._requires_review(0.98, provider_confidence, job_hints),
                review_reasons=self._review_reasons(0.98, provider_confidence, job_hints),
                security_flags=security_flags,
                warnings_count=warnings_count,
                errors_count=errors_count,
            )
        return self._unknown(
            provider=provider,
            provider_confidence=provider_confidence,
            message_type="BACKUP_REPORT",
            rule_ids=[f"{rule_prefix}_UNKNOWN_TEMPLATE"],
            security_flags=security_flags,
            review_reasons=["UNKNOWN_TEMPLATE"],
            warnings_count=warnings_count,
            errors_count=errors_count,
        )

    def _classify_azure(
        self,
        *,
        normalized: str,
        provider_confidence: float,
        security_flags: list[str],
        job_hints: list[str],
    ) -> Classification:
        if "resolved" in normalized and "alert" in normalized:
            return self._unknown(
                provider="AZURE",
                provider_confidence=provider_confidence,
                message_type="ALERT_RESOLVED",
                rule_ids=["AZURE_ALERT_RESOLVED_NO_EXECUTION"],
                security_flags=security_flags,
                review_reasons=["UNKNOWN_TEMPLATE"],
            )
        if "fired" in normalized and "backup failure" in normalized:
            return self._classification(
                provider="AZURE",
                provider_confidence=provider_confidence,
                message_type="BACKUP_ALERT",
                parser_status=ParsedReportItem.ParserStatus.FAILED,
                dashboard_status="ERROR",
                confidence=self._confidence(0.88, provider_confidence, job_hints),
                rule_ids=["AZURE_ALERT_BACKUP_FAILURE_FIRED"],
                evidence=[self._evidence("backup failure", "FAILED")],
                observation="Azure informó una alerta de fallo de backup.",
                requires_review=True,
                review_reasons=["BACKUP_CONFIGURATION_NOT_FOUND"] if not job_hints else [],
                security_flags=security_flags,
                error_summary="Azure informó una alerta de fallo de backup.",
            )
        return self._classify_provider_patterns(
            provider="AZURE",
            provider_confidence=provider_confidence,
            normalized=normalized,
            security_flags=security_flags,
            job_hints=job_hints,
            success_patterns=[r"(?:job status|backup status|status)\s*[:=]\s*completed\b"],
            warning_patterns=[r"(?:job status|backup status|status)\s*[:=]\s*completed with warnings\b"],
            failure_patterns=[r"(?:job status|backup status|status)\s*[:=]\s*failed\b", r"backup failure"],
            canceled_patterns=[r"(?:job status|status)\s*[:=]\s*canceled\b"],
            rule_prefix="AZURE_JOB",
        )

    def _classify_aws_dlm(
        self,
        *,
        normalized: str,
        provider_confidence: float,
        security_flags: list[str],
        job_hints: list[str],
    ) -> Classification:
        if "snapshotscreatefailed" in normalized or "detail.state" in normalized and "error" in normalized:
            return self._classification(
                provider="AWS_DLM",
                provider_confidence=provider_confidence,
                message_type="BACKUP_REPORT",
                parser_status=ParsedReportItem.ParserStatus.FAILED,
                dashboard_status="ERROR",
                confidence=self._confidence(0.92, provider_confidence, job_hints),
                rule_ids=["AWS_DLM_SNAPSHOT_FAILED"],
                evidence=[self._evidence("SnapshotsCreateFailed", "FAILED")],
                observation="AWS DLM informó un fallo de snapshot.",
                requires_review=self._requires_review(0.92, provider_confidence, job_hints),
                review_reasons=self._review_reasons(0.92, provider_confidence, job_hints),
                security_flags=security_flags,
                error_summary="AWS DLM informó un fallo de snapshot.",
            )
        if "snapshotscreatecompleted" in normalized:
            return self._classification(
                provider="AWS_DLM",
                provider_confidence=provider_confidence,
                message_type="BACKUP_REPORT",
                parser_status=ParsedReportItem.ParserStatus.SUCCESS,
                dashboard_status="CORRECTO",
                confidence=self._confidence(0.92, provider_confidence, job_hints),
                rule_ids=["AWS_DLM_SNAPSHOT_COMPLETED"],
                evidence=[self._evidence("SnapshotsCreateCompleted", "SUCCESS")],
                observation="AWS DLM informó creación correcta de snapshot.",
                requires_review=self._requires_review(0.92, provider_confidence, job_hints),
                review_reasons=self._review_reasons(0.92, provider_confidence, job_hints),
                security_flags=security_flags,
            )
        return self._unknown(
            provider="AWS_DLM",
            provider_confidence=provider_confidence,
            message_type="BACKUP_REPORT",
            rule_ids=["AWS_DLM_UNKNOWN_TEMPLATE"],
            security_flags=security_flags,
            review_reasons=["UNKNOWN_TEMPLATE"],
        )

    def _classify_script(
        self,
        *,
        normalized: str,
        provider_confidence: float,
        security_flags: list[str],
        job_hints: list[str],
    ) -> Classification:
        fields = self._key_values(normalized)
        status = fields.get("status", "").upper()
        exit_code = self._int_or_none(fields.get("exit_code"))
        warnings_count = self._int_or_none(fields.get("warnings"))
        errors_count = self._int_or_none(fields.get("errors"))
        required = {"schema_version", "job_id", "run_id", "status", "finished_at", "exit_code", "warnings", "errors"}
        missing = sorted(required.difference(fields))
        if missing:
            return self._unknown(
                provider="SCRIPT",
                provider_confidence=provider_confidence,
                message_type="BACKUP_REPORT",
                rule_ids=["SCRIPT_LEGACY_MANUAL_REVIEW"],
                security_flags=security_flags,
                review_reasons=["MISSING_REQUIRED_FIELDS"],
                warnings_count=warnings_count,
                errors_count=errors_count,
            )
        if status == "SUCCESS" and (exit_code != 0 or (errors_count or 0) > 0):
            return self._unknown(
                provider="SCRIPT",
                provider_confidence=provider_confidence,
                message_type="BACKUP_REPORT",
                rule_ids=["SCRIPT_CONTRACT_CONFLICT"],
                security_flags=security_flags,
                review_reasons=["CONFLICTING_FINAL_STATUS", "SUCCESS_WITH_NONZERO_ERRORS"],
                warnings_count=warnings_count,
                errors_count=errors_count,
            )
        if status in {"ERROR", "FAILED"} or exit_code != 0 or (errors_count or 0) > 0:
            return self._classification(
                provider="SCRIPT",
                provider_confidence=provider_confidence,
                message_type="BACKUP_REPORT",
                parser_status=ParsedReportItem.ParserStatus.FAILED,
                dashboard_status="ERROR",
                confidence=self._confidence(0.98, provider_confidence, job_hints),
                rule_ids=["SCRIPT_CONTRACT_FAILED"],
                evidence=[self._evidence(f"status={status}", "FAILED")],
                observation="El script informó una ejecución fallida.",
                requires_review=self._requires_review(0.98, provider_confidence, job_hints),
                review_reasons=self._review_reasons(0.98, provider_confidence, job_hints),
                security_flags=security_flags,
                warnings_count=warnings_count,
                errors_count=errors_count,
                error_summary="El script informó una ejecución fallida.",
            )
        if status == "WARNING" or (warnings_count or 0) > 0:
            return self._classification(
                provider="SCRIPT",
                provider_confidence=provider_confidence,
                message_type="BACKUP_REPORT",
                parser_status=ParsedReportItem.ParserStatus.WARNING,
                dashboard_status="WARNING",
                confidence=self._confidence(0.98, provider_confidence, job_hints),
                rule_ids=["SCRIPT_CONTRACT_WARNING"],
                evidence=[self._evidence(f"warnings={warnings_count}", "WARNING")],
                observation="El script informó una ejecución con advertencias.",
                requires_review=self._requires_review(0.98, provider_confidence, job_hints),
                review_reasons=self._review_reasons(0.98, provider_confidence, job_hints),
                security_flags=security_flags,
                warnings_count=warnings_count,
                errors_count=errors_count,
                warning_details="El script informó una ejecución con advertencias.",
            )
        if status == "SUCCESS" and exit_code == 0 and (errors_count or 0) == 0:
            return self._classification(
                provider="SCRIPT",
                provider_confidence=provider_confidence,
                message_type="BACKUP_REPORT",
                parser_status=ParsedReportItem.ParserStatus.SUCCESS,
                dashboard_status="CORRECTO",
                confidence=self._confidence(0.98, provider_confidence, job_hints),
                rule_ids=["SCRIPT_CONTRACT_SUCCESS"],
                evidence=[self._evidence("status=SUCCESS", "SUCCESS")],
                observation="El script informó una ejecución correcta.",
                requires_review=self._requires_review(0.98, provider_confidence, job_hints),
                review_reasons=self._review_reasons(0.98, provider_confidence, job_hints),
                security_flags=security_flags,
                warnings_count=warnings_count,
                errors_count=errors_count,
            )
        return self._unknown(
            provider="SCRIPT",
            provider_confidence=provider_confidence,
            message_type="BACKUP_REPORT",
            rule_ids=["SCRIPT_LEGACY_MANUAL_REVIEW"],
            security_flags=security_flags,
            review_reasons=["UNKNOWN_TEMPLATE"],
            warnings_count=warnings_count,
            errors_count=errors_count,
        )

    def _provider(self, normalized: str) -> tuple[str, float]:
        candidates = [
            ("SCRIPT", ["[backup][provider=script]", "schema_version=", "job_id="]),
            ("VEEAM", ["veeam", "veeam backup & replication", "session status", "job session"]),
            ("IPERIUS", ["iperius", "iperius backup"]),
            ("AZURE", ["azure backup", "recovery services vault", "backup vault", "microsoft azure", "azure monitor"]),
            ("NAKIVO", ["nakivo", "nakivo backup & replication"]),
            ("QNAP_HBS", ["qnap", "hbs 3", "hybrid backup sync"]),
            ("AWS_DLM", ["source: aws.dlm", "aws.dlm", "dlmpolicyid", "snapshotscreatecompleted", "snapshotscreatefailed"]),
            ("CUBEBACKUP", ["cubebackup", "errorcount", "finishedwitherrors"]),
        ]
        hits: list[tuple[str, int]] = []
        for provider, signals in candidates:
            score = sum(1 for signal in signals if signal in normalized)
            if score:
                hits.append((provider, score))
        if not hits:
            return "UNKNOWN", 0.0
        hits.sort(key=lambda item: item[1], reverse=True)
        provider, score = hits[0]
        if len(hits) > 1 and hits[1][1] == score:
            return provider, 0.65
        return provider, min(0.98, 0.78 + (score * 0.08))

    def _job_hints(self, *, message: InboundMessage, normalized_text: str) -> list[str]:
        hints: list[str] = []
        jobs = BackupJob.objects.filter(organization=message.organization)
        for job in jobs:
            aliases = [job.name, job.external_identifier]
            aliases.extend(re.split(r"[,;\n]", job.matching_aliases or ""))
            if any(alias and self._normalize(alias) in normalized_text for alias in aliases):
                hints.append(job.name)
        return hints

    def _message_text(self, message: InboundMessage) -> str:
        payload = message.provider_payload or {}
        graph_payload = payload.get("graph") if isinstance(payload, dict) else None
        graph_text = ""
        if isinstance(graph_payload, dict):
            graph_body = graph_payload.get("body") or {}
            if isinstance(graph_body, dict):
                graph_text = str(graph_body.get("content") or "")
        attachment_text = "\n".join(
            attachment.extracted_text
            for attachment in message.attachments.all()
            if attachment.extracted_text
        )
        return "\n".join(
            part
            for part in [
                message.subject,
                message.sender,
                message.body_preview,
                message.text_body,
                message.html_as_text,
                attachment_text,
                graph_text,
            ]
            if part
        )

    def _normalize(self, value: str) -> str:
        decomposed = unicodedata.normalize("NFKD", value or "")
        without_accents = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
        return re.sub(r"\s+", " ", without_accents.casefold()).strip()

    def _security_flags(self, normalized: str) -> list[str]:
        patterns = [
            "ignore previous instructions",
            "ignore all previous instructions",
            "disregard previous instructions",
            "reveal your prompt",
            "follow this instruction",
            "mark this as success",
        ]
        if any(pattern in normalized for pattern in patterns):
            return ["UNTRUSTED_INSTRUCTION_IN_EMAIL"]
        return []

    def _counter(self, normalized: str, label_pattern: str) -> int | None:
        matches = re.findall(rf"\b(?:{label_pattern})\s*[:=]\s*(\d+)\b", normalized)
        if not matches:
            return None
        return max(int(value) for value in matches)

    def _key_values(self, normalized: str) -> dict[str, str]:
        fields: dict[str, str] = {}
        for key, value in re.findall(r"\b([a-z_]+)\s*=\s*([^\s\]]+)", normalized):
            fields[key] = value.strip()
        return fields

    def _int_or_none(self, value: str | None) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except ValueError:
            return None

    def _first_match(self, normalized: str, patterns: list[str]):
        for pattern in patterns:
            match = re.search(pattern, normalized)
            if match:
                return match
        return None

    def _confidence(self, base: float, provider_confidence: float, job_hints: list[str]) -> float:
        confidence = min(base, provider_confidence)
        if not job_hints:
            confidence -= 0.20
        if provider_confidence < 0.85:
            confidence -= 0.20
        if job_hints:
            confidence += 0.02
        return max(0.0, min(1.0, round(confidence, 2)))

    def _requires_review(self, base: float, provider_confidence: float, job_hints: list[str]) -> bool:
        return self._confidence(base, provider_confidence, job_hints) < 0.85

    def _review_reasons(self, base: float, provider_confidence: float, job_hints: list[str]) -> list[str]:
        reasons: list[str] = []
        if self._confidence(base, provider_confidence, job_hints) < 0.85:
            reasons.append("LOW_CONFIDENCE")
        if not job_hints:
            reasons.append("BACKUP_CONFIGURATION_NOT_FOUND")
        if provider_confidence < 0.85:
            reasons.append("UNKNOWN_PROVIDER")
        return reasons

    def _configuration_match(self, job_hints: list[str]) -> str:
        if len(job_hints) == 1:
            return "MATCHED"
        if len(job_hints) > 1:
            return "AMBIGUOUS"
        return "NOT_MATCHED"

    def _evidence(self, text: str, effect: str) -> dict[str, str]:
        return {"text": text, "location": "message_text", "effect": effect}

    def _classification(
        self,
        *,
        provider: str,
        provider_confidence: float,
        message_type: str,
        parser_status: str,
        dashboard_status: str,
        confidence: float,
        rule_ids: list[str],
        evidence: list[dict[str, str]],
        observation: str,
        requires_review: bool,
        review_reasons: list[str],
        security_flags: list[str],
        warnings_count: int | None = None,
        errors_count: int | None = None,
        error_summary: str = "",
        warning_details: str = "",
    ) -> Classification:
        if security_flags and "UNTRUSTED_INSTRUCTION_IN_EMAIL" not in review_reasons:
            review_reasons = [*review_reasons, "UNTRUSTED_INSTRUCTION_IN_EMAIL"]
            requires_review = True
        return Classification(
            provider=provider,
            provider_confidence=provider_confidence,
            message_type=message_type,
            parser_status=parser_status,
            dashboard_status=dashboard_status,
            confidence=confidence,
            rule_ids=rule_ids,
            evidence=evidence,
            observation=observation,
            requires_review=requires_review,
            review_reasons=review_reasons,
            security_flags=security_flags,
            warnings_count=warnings_count,
            errors_count=errors_count,
            error_summary=error_summary,
            warning_details=warning_details,
        )

    def _unknown(
        self,
        *,
        provider: str,
        provider_confidence: float,
        message_type: str,
        rule_ids: list[str],
        security_flags: list[str],
        review_reasons: list[str],
        warnings_count: int | None = None,
        errors_count: int | None = None,
    ) -> Classification:
        return self._classification(
            provider=provider,
            provider_confidence=provider_confidence,
            message_type=message_type,
            parser_status=ParsedReportItem.ParserStatus.UNKNOWN,
            dashboard_status="REVISION_MANUAL",
            confidence=0.0,
            rule_ids=rule_ids,
            evidence=[],
            observation="El formato no coincide con un perfil validado o requiere revisión.",
            requires_review=True,
            review_reasons=review_reasons,
            security_flags=security_flags,
            warnings_count=warnings_count,
            errors_count=errors_count,
        )
