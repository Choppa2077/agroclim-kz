"""Optional plotting helpers (requires the ``plot`` extra)."""

from __future__ import annotations

from pathlib import Path

from agroclim.optimizer import Recommendation

__all__ = ["save_response_curve"]


def save_response_curve(recommendation: Recommendation, path: str | Path) -> Path:
    """Save the predicted-yield response curve of a recommendation as a PNG.

    Raises:
        RuntimeError: if matplotlib is not installed.
    """
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError as exc:  # pragma: no cover - exercised only without the extra
        raise RuntimeError(
            "plotting requires matplotlib; install it with: pip install 'agroclim[plot]'"
        ) from exc

    days = [doy for doy, _ in recommendation.curve]
    yields = [value for _, value in recommendation.curve]
    low, high = recommendation.literature_window

    figure, axes = plt.subplots(figsize=(7.0, 4.0))
    axes.plot(days, yields, color="#2F6B4F", linewidth=2)
    axes.axvspan(low, high, color="#2F6B4F", alpha=0.12, label="published window")
    axes.axvline(
        recommendation.day_of_year,
        color="#1E2A30",
        linestyle="--",
        linewidth=1.2,
        label=f"recommended (DOY {recommendation.day_of_year})",
    )
    axes.set_xlabel("sowing day of year")
    axes.set_ylabel("predicted yield, t/ha")
    axes.set_title(f"{recommendation.crop}: yield response to the sowing date")
    axes.grid(linestyle=":", color="0.7")
    axes.legend(loc="lower center", fontsize=8, frameon=False)
    figure.tight_layout()

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(target, dpi=200)
    plt.close(figure)
    return target
