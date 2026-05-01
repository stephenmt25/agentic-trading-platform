/**
 * Largest-Triangle-Three-Buckets (LTTB) downsampling.
 *
 * Keeps the visual shape of a time-series while reducing point count for rendering.
 * Compared to uniform stride sampling, LTTB preserves peaks/troughs that drive
 * the reader's interpretation of the chart. Linear in input size.
 *
 * Reference: Sveinn Steinarsson, "Downsampling Time Series for Visual Representation"
 * MSc thesis, University of Iceland, 2013.
 */

const DEFAULT_MAX_POINTS = 500;

/**
 * 1D variant: input is a number[] where index is treated as the x coordinate.
 * Returns a new array of at most `threshold` points.
 * If input is already <= threshold, returns the original array (by reference).
 */
export function lttb(data: number[], threshold: number = DEFAULT_MAX_POINTS): number[] {
  if (threshold >= data.length || threshold <= 2) return data;

  const sampled: number[] = new Array(threshold);
  const bucketSize = (data.length - 2) / (threshold - 2);

  // First point is always kept
  let a = 0;
  sampled[0] = data[a];

  for (let i = 0; i < threshold - 2; i++) {
    // Bucket average (centroid of the NEXT bucket, used as the third triangle vertex)
    const avgRangeStart = Math.floor((i + 1) * bucketSize) + 1;
    let avgRangeEnd = Math.floor((i + 2) * bucketSize) + 1;
    if (avgRangeEnd > data.length) avgRangeEnd = data.length;
    const avgRangeLength = avgRangeEnd - avgRangeStart;

    let avgX = 0;
    let avgY = 0;
    for (let j = avgRangeStart; j < avgRangeEnd; j++) {
      avgX += j;
      avgY += data[j];
    }
    avgX /= avgRangeLength;
    avgY /= avgRangeLength;

    // Current bucket range
    const rangeOffs = Math.floor(i * bucketSize) + 1;
    const rangeTo = Math.floor((i + 1) * bucketSize) + 1;

    const pointAX = a;
    const pointAY = data[a];

    let maxArea = -1;
    let maxAreaPoint = rangeOffs;
    for (let j = rangeOffs; j < rangeTo; j++) {
      const area =
        Math.abs(
          (pointAX - avgX) * (data[j] - pointAY) - (pointAX - j) * (avgY - pointAY)
        ) * 0.5;
      if (area > maxArea) {
        maxArea = area;
        maxAreaPoint = j;
      }
    }

    sampled[i + 1] = data[maxAreaPoint];
    a = maxAreaPoint;
  }

  // Last point is always kept
  sampled[threshold - 1] = data[data.length - 1];
  return sampled;
}

/**
 * 2D variant: input is an array of {x, y} points. Use when x-axis is non-uniform
 * (e.g., timestamps with gaps).
 */
export interface XYPoint {
  x: number;
  y: number;
}

export function lttbXY(data: XYPoint[], threshold: number = DEFAULT_MAX_POINTS): XYPoint[] {
  if (threshold >= data.length || threshold <= 2) return data;

  const sampled: XYPoint[] = new Array(threshold);
  const bucketSize = (data.length - 2) / (threshold - 2);

  let a = 0;
  sampled[0] = data[a];

  for (let i = 0; i < threshold - 2; i++) {
    const avgRangeStart = Math.floor((i + 1) * bucketSize) + 1;
    let avgRangeEnd = Math.floor((i + 2) * bucketSize) + 1;
    if (avgRangeEnd > data.length) avgRangeEnd = data.length;
    const avgRangeLength = avgRangeEnd - avgRangeStart;

    let avgX = 0;
    let avgY = 0;
    for (let j = avgRangeStart; j < avgRangeEnd; j++) {
      avgX += data[j].x;
      avgY += data[j].y;
    }
    avgX /= avgRangeLength;
    avgY /= avgRangeLength;

    const rangeOffs = Math.floor(i * bucketSize) + 1;
    const rangeTo = Math.floor((i + 1) * bucketSize) + 1;

    const pointAX = data[a].x;
    const pointAY = data[a].y;

    let maxArea = -1;
    let maxAreaPoint = rangeOffs;
    for (let j = rangeOffs; j < rangeTo; j++) {
      const dX = data[j].x;
      const dY = data[j].y;
      const area =
        Math.abs(
          (pointAX - avgX) * (dY - pointAY) - (pointAX - dX) * (avgY - pointAY)
        ) * 0.5;
      if (area > maxArea) {
        maxArea = area;
        maxAreaPoint = j;
      }
    }

    sampled[i + 1] = data[maxAreaPoint];
    a = maxAreaPoint;
  }

  sampled[threshold - 1] = data[data.length - 1];
  return sampled;
}

export { DEFAULT_MAX_POINTS };
