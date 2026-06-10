from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class Alert:
    key: str
    alert_type: str
    game_pk: int | None
    message: str
    group_key: str | None = None
    priority: int = 100
    detail_order: int | None = None
    detail_key: str | None = None
    detail_text: str | None = None


@dataclass(frozen=True)
class AlertBatch:
    key: str
    alert_type: str
    game_pk: int | None
    message: str
    components: tuple[Alert, ...]

    @property
    def keys_to_mark(self) -> tuple[str, ...]:
        keys = [self.key]
        keys.extend(alert.key for alert in self.components)
        return tuple(dict.fromkeys(keys))


def consolidate_alerts(alerts: Iterable[Alert]) -> list[AlertBatch]:
    grouped: dict[str, list[tuple[int, Alert]]] = {}
    standalone: dict[int, Alert] = {}
    output_order: list[tuple[str, str | int]] = []

    for index, alert in enumerate(alerts):
        if alert.group_key:
            if alert.group_key not in grouped:
                output_order.append(("group", alert.group_key))
            grouped.setdefault(alert.group_key, []).append((index, alert))
        else:
            standalone[index] = alert
            output_order.append(("standalone", index))

    batches: list[AlertBatch] = []
    for kind, key in output_order:
        if kind == "standalone":
            alert = standalone[int(key)]
            batches.append(
                AlertBatch(
                    key=alert.key,
                    alert_type=alert.alert_type,
                    game_pk=alert.game_pk,
                    message=alert.message,
                    components=(alert,),
                )
            )
            continue

        group_key = str(key)
        batches.append(_consolidated_group(group_key, grouped[group_key]))
    return batches


def _consolidated_group(group_key: str, alerts: list[tuple[int, Alert]]) -> AlertBatch:
    ordered = sorted(alerts, key=lambda item: item[0])
    primary = min(ordered, key=lambda item: (item[1].priority, item[0]))[1]
    details = _secondary_details(ordered, primary)
    suffix = f" | {' | '.join(details)}" if details else ""
    return AlertBatch(
        key=group_key,
        alert_type=primary.alert_type,
        game_pk=primary.game_pk,
        message=f"{primary.message}{suffix}",
        components=tuple(alert for _, alert in ordered),
    )


def _secondary_details(
    alerts: list[tuple[int, Alert]], primary: Alert
) -> list[str]:
    by_key: dict[str, tuple[int, int, str]] = {}
    for position, alert in alerts:
        if alert is primary or alert.detail_order is None or not alert.detail_text:
            continue
        detail_key = alert.detail_key or alert.key
        candidate = (alert.detail_order, position, alert.detail_text)
        existing = by_key.get(detail_key)
        if existing is None or candidate[:2] < existing[:2]:
            by_key[detail_key] = candidate
    return [detail for _, _, detail in sorted(by_key.values())]
