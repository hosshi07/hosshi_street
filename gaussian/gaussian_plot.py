"""
Generate one random dataset, then plot its distribution as a Gaussian.

Outputs: gaussian_distribution.png (in the same directory as this script)
"""

import random
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# --- 1) Make one set of random data -------------------------------------------
seed = random.randrange(1_000_000)          # a fresh random seed every run
rng = np.random.default_rng(seed)

n = 1000
data = rng.normal(loc=rng.uniform(-5, 5), scale=rng.uniform(0.5, 3.0), size=n)
# ^ one draw: random centre + random width, so the shape differs each run

mu = float(np.mean(data))
sigma = float(np.std(data))

# --- 2) Plot the distribution as a Gaussian -----------------------------------
fig, ax = plt.subplots(figsize=(9, 5.5), dpi=140)

counts, edges, patches = ax.hist(data, bins=40, color="#4C8FBD", alpha=0.55,
                                 edgecolor="white", label="random data (n=%d)" % n)

x = np.linspace(data.min(), data.max(), 400)
# scale the Gaussian PDF to the histogram area, so both overlays share one axis
scale = n * (edges[1] - edges[0])
peak = scale / (sigma * np.sqrt(2 * np.pi))
ymax = max(float(counts.max()), peak)
ax.set_ylim(0, ymax * 1.18)
ax.plot(x, scale * np.exp(-0.5 * ((x - mu) / sigma) ** 2) / (sigma * np.sqrt(2 * np.pi)),
        color="#D72634", lw=2.2, label="Gaussian fit")
# shade the mu +/- 1 sigma band and mark mean / sigma ticks
ax.axvspan(mu - sigma, mu + sigma, color="#2E8B57", alpha=0.10,
           label="mu +/- 1 sigma")
ax.axvline(mu, color="#2E8B57", lw=1.6, ls="--", label="mean = mu")
ax.annotate("", xy=(mu + sigma, ymax * 0.94), xytext=(mu - sigma, ymax * 0.94),
            arrowprops=dict(arrowstyle="<->", color="#2E8B57", lw=1.2))
ax.text(mu, ymax * 0.96, "1 sigma", ha="center", color="#2E8B57")

ax.set_title("Gaussian distribution of random data (seed=%d)" % seed)
ax.set_xlabel("value")
ax.set_ylabel("count")
ax.legend(loc="upper left", frameon=False)
ax.grid(alpha=0.25)
fig.tight_layout()

out = fig.savefig("gaussian_distribution.png")
print("seed=%d  n=%d  mean=%.4f  std=%.4f  range=[%.3f, %.3f]"
      % (seed, n, mu, sigma, data.min(), data.max()))
print("wrote:", out)
