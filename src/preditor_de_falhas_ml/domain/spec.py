"""Especificação de uma medição de ping e filtros de consulta."""

from dataclasses import dataclass

from preditor_de_falhas_ml.domain.ids import MeasurementId, ProbeId, require_int


@dataclass(frozen=True, slots=True)
class CountrySelection:
    """Quantidade de probes em um país ISO de duas letras."""

    country_code: str
    probe_count: int = 1

    def __post_init__(self) -> None:
        code = self.country_code
        if (
            not isinstance(code, str)
            or len(code.strip()) != 2
            or not code.strip().isascii()
            or not code.strip().isalpha()
        ):
            raise ValueError(
                f"country_code inválido: {code!r}. "
                "Informe um código de país com duas letras, como 'BR'."
            )
        object.__setattr__(self, "country_code", code.strip().upper())
        require_int(self.probe_count, "probe_count", minimum=1)


@dataclass(frozen=True, slots=True)
class ProbeIdSelection:
    """Lista não vazia de IDs de probes distintos."""

    probe_ids: tuple[int, ...]

    def __post_init__(self) -> None:
        probes = self.probe_ids
        if (
            not isinstance(probes, tuple)
            or not probes
            or any(type(probe) is not int or probe <= 0 for probe in probes)
            or len(set(probes)) != len(probes)
        ):
            raise ValueError(
                f"probe_ids inválido: {probes!r}. "
                "Informe IDs inteiros positivos distintos."
            )


@dataclass(frozen=True, slots=True)
class MeasurementSpec:
    """Pedido de ping ICMP: alvo, família, probes e janela temporal.

    ``interval`` e ``duration`` vêm juntos (medição recorrente) ou os dois
    ausentes (one-off). A CLI preenche os defaults; este tipo não assume
    8.8.8.8.
    """

    target: str
    address_family: int
    selection: CountrySelection | ProbeIdSelection
    packets: int = 16
    size: int = 64
    interval: int | None = None
    duration: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.target, str) or not self.target.strip():
            raise ValueError(
                f"target inválido: {self.target!r}. Informe um host ou endereço."
            )
        object.__setattr__(self, "target", self.target.strip())
        if self.address_family not in (4, 6):
            raise ValueError(
                f"af inválido: {self.address_family!r}. Use 4 (IPv4) ou 6 (IPv6)."
            )
        require_int(self.packets, "packets", minimum=1)
        if self.packets > 16:
            raise ValueError(
                f"packets inválido: {self.packets!r}. Informe um inteiro entre 1 e 16."
            )
        require_int(self.size, "size", minimum=1)
        if (self.interval is None) != (self.duration is None):
            raise ValueError(
                f"interval/duration inválidos: {self.interval!r}/{self.duration!r}. "
                "Informe os dois para medição recorrente, ou nenhum para one-off."
            )
        if self.interval is not None:
            require_int(self.interval, "interval", minimum=1)
            require_int(self.duration, "duration", minimum=1)

    @property
    def is_oneoff(self) -> bool:
        return self.interval is None

    def as_configuration(self) -> dict[str, object]:
        """Serializa o pedido para o histórico, sem credenciais."""
        configuration: dict[str, object] = {
            "target": self.target,
            "af": self.address_family,
            "type": "ping",
            "size": self.size,
            "packets": self.packets,
            "is_oneoff": self.is_oneoff,
            "interval": self.interval,
            "duration": self.duration,
        }
        if isinstance(self.selection, CountrySelection):
            configuration["country_code"] = self.selection.country_code
            configuration["probe_count"] = self.selection.probe_count
            configuration["probe_ids"] = None
        else:
            configuration["country_code"] = None
            configuration["probe_count"] = len(self.selection.probe_ids)
            configuration["probe_ids"] = list(self.selection.probe_ids)
        return configuration


@dataclass(frozen=True, slots=True)
class MeasurementDefinition:
    """Definição já criada no Atlas, usada como contexto dos resultados."""

    measurement_id: MeasurementId
    type: str
    target: str
    address_family: int
    size: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.type, str) or not self.type:
            raise ValueError(
                f"type inválido: {self.type!r}. Selecione uma medição de ping."
            )
        if not isinstance(self.target, str) or not self.target.strip():
            raise ValueError(
                f"target inválido: {self.target!r}. Informe o alvo da medição."
            )
        if self.address_family not in (4, 6):
            raise ValueError(
                f"af inválido: {self.address_family!r}. Use 4 (IPv4) ou 6 (IPv6)."
            )
        if self.size is not None:
            require_int(self.size, "size")


@dataclass(frozen=True, slots=True)
class ResultFilters:
    """Filtros opcionais da consulta de resultados (probe e período Unix)."""

    probe_id: ProbeId | None = None
    start: int | None = None
    stop: int | None = None

    def __post_init__(self) -> None:
        if self.start is not None:
            require_int(self.start, "start")
        if self.stop is not None:
            require_int(self.stop, "stop")
        if self.start is not None and self.stop is not None and self.stop < self.start:
            raise ValueError(
                f"stop inválido: {self.stop!r}. Informe um instante maior ou igual a start={self.start}."
            )
