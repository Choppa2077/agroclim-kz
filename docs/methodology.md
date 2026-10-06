# Methodology

This document records where every constant in `agroclim.model` comes from, so
that a reviewer can check a recommendation without reading the code.

## 1. Scope

The package covers **rainfed spring crops of the Akmola oblast**, calibrated on
Field No. 5 of the A.I. Barayev Research and Production Centre for Grain
Farming (51.5864 N, 70.8406 E). The climate is continental semi-arid
(Köppen BSk): 300–350 mm of annual precipitation and a growing season of about
130 days, from May to September. Soils are southern chernozems, pH 6.5–7.5,
2.0–2.5 % organic carbon.

## 2. Season predictors

`agroclim.climate` reduces daily records to four season-level values over
1 May – 31 August:

| Predictor | Definition |
|---|---|
| `t_mean` | mean daily air temperature at 2 m, °C |
| `precipitation_total` | sum of corrected daily precipitation, mm |
| `relative_humidity_mean` | mean relative humidity at 2 m, % |
| `gdd` | sum of `max(T − base, 0)` over the season, base 0 °C by default |

Days carrying the NASA POWER missing flag (−999) are dropped before
aggregation rather than imputed, so a gap shortens the season instead of
inventing a value.

## 3. Yield model

```
yield = base × (1 + rotation) × f_precip × f_humidity × f_nitrogen × f_pH × f_sowing
```

The result is clipped to the physically plausible range 0.05–2.2 t/ha.

### 3.1 Base yields

| Crop | Base, t/ha | Optimum DOY | Published window (DOY) |
|---|---|---|---|
| Spring wheat | 1.020 | 135 (15 May) | 130–150 |
| Barley | 0.935 | 120 (30 Apr) | 115–135 |
| Field pea | 0.765 | 120 | 110–130 |
| Lentil | 0.680 | 135 | 120–150 |
| Canola | 0.595 | 128 | 128–148 |
| Flax | 0.510 | 135 | 135–155 |

Base yields follow the district statistics used in the source paper; the
windows follow the multi-year trials at the Shortandy station and the canola
literature (Kondra 1977; Degenhardt & Kondra 1981; Lilley et al. 2019).

### 3.2 Rotation

| Preceding crop | Effect |
|---|---|
| Fallow | +35 % |
| Legume (pea, lentil) | +11 % |
| Oilseed (canola, flax) | 0 % |
| Other cereal | −5 % |
| The same crop | −15 % |

Sources: fallow effect on spring wheat in Northern Kazakhstan (Solovyov et al.
2024, +30–42 %); legume predecessor (Gill 2018, +11 %; Zhao et al. 2022
meta-analysis, +20 % on average); continuous cereal cropping (Woźniak 2019,
−8…−32 %). The package uses the conservative end of each published range.

### 3.3 Precipitation

Piecewise-linear, calibrated on the **district median of 139 mm**, not on the
200–300 mm assumed by most temperate-zone sources:

| Season precipitation, mm | Factor |
|---|---|
| ≤ 60 | 0.40 |
| 100 | 0.45 |
| 139 (median) | 1.00 |
| 170 | 1.10 |
| ≥ 250 | 1.30 |

A regression of 21 years of official Shortandy yields on growing-season
precipitation and humidity explains R² = 0.46 of the real variance, which is
why these two factors dominate the formula.

### 3.4 Humidity, nitrogen and pH

| Input | Rule |
|---|---|
| Relative humidity | 0.80 at 35 %, 0.90 at 45 %, 1.00 at 55 %, 1.15 at 65 % |
| Soil nitrogen | 0.80 below 80 ppm, 1.00 at 120 ppm, 1.05 at 160 ppm |
| Soil pH | 1.00 inside 6.5–7.5, −10 % per pH unit outside, floor 0.70 |

### 3.5 Sowing date

```
f_sowing = max(0.60, 1 − 0.12 × ((doy − optimum) / 30)²)
```

The response is deliberately shallow: in the source study the sowing date moves
the predicted yield by about 0.07 t/ha across the whole window, against 0.61
t/ha for precipitation. It is nevertheless the factor the farmer controls.

## 4. Prediction interval

At sowing time the coming season is unknown, so the interval is **not** a
confidence interval of the fitted parameters. The optimizer resamples the two
dominant inputs — precipitation with a coefficient of variation of 0.25 and
humidity with a standard deviation of 3 percentage points, both taken from the
1991–2025 record — and reports the 5th and 95th percentiles of the resulting
yields. The sampler is seeded (`--seed`), so a recommendation is reproducible.

## 5. Limitations

1. The constants are calibrated on one research station; another oblast needs
   recalibration before the numbers mean anything.
2. Management variables — fertiliser rate, cultivar, tillage — are absent, and
   in the source study they are the most credible explanation of the years the
   model missed.
3. SoilGrids gives a static soil snapshot, while pH and nitrogen change with
   tillage and fertilisation.
4. The optimizer uses the user's season estimate (typically a climatological
   mean), not a seasonal forecast.
5. The sowing-date response is a smooth analytic curve, not a fitted one; it
   reproduces the direction and magnitude reported in the paper, not its exact
   shape.

## 6. References

1. M. Idrissov, N. Kashkimbayeva, D. Kaibassova. Determining the Optimal
   Planting Time for Agricultural Crops in Northern Kazakhstan. IEEE SIST 2026.
2. Z. P. Kondra. Effects of planting date on rapeseed. *Can. J. Plant Sci.* 57,
   607–609, 1977.
3. D. F. Degenhardt, Z. P. Kondra. The influence of seeding date and rate on
   *Brassica napus*. *Can. J. Plant Sci.* 61, 175–183, 1981.
4. K. S. Gill. Wheat yield response to agronomic practices in northern Alberta.
   *Can. J. Plant Sci.* 98(4), 1139–1149, 2018.
5. J. Zhao et al. Does crop rotation yield more in China? A meta-analysis.
   *Nature Communications* 13, 4926, 2022.
6. A. Woźniak. Effect of crop rotation and cereal monoculture on yield and
   quality of winter wheat. *Eur. J. Agron.* 109, 125925, 2019.
7. V. V. Solovyov et al. Fallow effects on spring wheat in northern Kazakhstan.
   *Int. J. Design Nature Ecodynamics* 19(1), 137–146, 2024.
8. J. M. Lilley et al. Defining optimal sowing and flowering periods for canola
   in Australia. *Field Crops Res.* 235, 118–128, 2019.
9. L. Poggio et al. SoilGrids 2.0. *SOIL* 7, 217–240, 2021.
10. NASA POWER Project. https://power.larc.nasa.gov/
