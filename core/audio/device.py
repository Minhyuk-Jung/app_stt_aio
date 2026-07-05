"""Input device enumeration and selection."""

from __future__ import annotations

from dataclasses import dataclass

import sounddevice as sd

from core.audio.errors import DeviceAccessError, DeviceNotFoundError


@dataclass(frozen=True)
class DeviceInfo:
    id: int
    name: str
    is_default: bool
    default_samplerate: float
    max_input_channels: int
    supported_samplerates: tuple[int, ...]


def _supported_samplerates(default_rate: float) -> tuple[int, ...]:
    candidates = {16000, 44100, 48000, int(default_rate)}
    return tuple(sorted(rate for rate in candidates if rate > 0))


def list_devices() -> list[DeviceInfo]:
    hostapis = sd.query_hostapis()
    try:
        default_input = sd.default.device[0]
    except Exception:
        default_input = -1
    if default_input is None or default_input < 0:
        default_input = -1
    devices: list[DeviceInfo] = []
    for index, info in enumerate(sd.query_devices()):
        if info["max_input_channels"] <= 0:
            continue
        hostapi_name = hostapis[info["hostapi"]]["name"]
        devices.append(
            DeviceInfo(
                id=index,
                name=f"{info['name']} ({hostapi_name})",
                is_default=default_input >= 0 and index == default_input,
                default_samplerate=float(info["default_samplerate"]),
                max_input_channels=int(info["max_input_channels"]),
                supported_samplerates=_supported_samplerates(
                    float(info["default_samplerate"])
                ),
            )
        )
    return devices


def resolve_device_id(device_id: str | int | None) -> int | None:
    if device_id is None:
        return None
    if isinstance(device_id, int):
        return device_id
    text = str(device_id).strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError as exc:
        raise DeviceNotFoundError(f"invalid device id: {device_id}") from exc


def validate_device(device_id: int | None) -> int | None:
    if device_id is None:
        return None
    devices = {item.id: item for item in list_devices()}
    if device_id not in devices:
        raise DeviceNotFoundError(f"input device not found: {device_id}")
    return device_id


def open_input_stream_kwargs(
    device_id: int | None,
    *,
    channels: int = 1,
    dtype: str = "int16",
) -> dict:
    try:
        if device_id is None:
            info = sd.query_devices(kind="input")
        else:
            info = sd.query_devices(device_id)
    except sd.PortAudioError as exc:
        raise DeviceAccessError(str(exc)) from exc

    if info["max_input_channels"] <= 0:
        raise DeviceNotFoundError("selected device has no input channels")

    stream_channels = min(channels, int(info["max_input_channels"]))
    samplerate = int(info["default_samplerate"])
    if samplerate <= 0:
        raise DeviceAccessError("device reports invalid default sample rate")

    return {
        "device": device_id,
        "channels": stream_channels,
        "samplerate": samplerate,
        "dtype": dtype,
    }
