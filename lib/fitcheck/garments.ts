/**
 * Curated garment size charts, embedded for the in-browser fit check.
 *
 * Mirrors cv/garments/*.json. The fit check runs entirely client-side (no
 * backend), so the charts the sizing scores against live here. Chest/shoulder
 * ranges are the BODY measurements (cm) each size fits, same as the Python
 * `size_chart.py`.
 */

export interface SizeRange {
  chest_cm: [number, number];
  shoulder_cm?: [number, number];
}
export type SizeChart = Record<string, SizeRange>;

export interface Garment {
  id: string;
  name: string;
  brand: string;
  category: string; // top | bottom | ...
  fit: string; // oversized | regular | slim
  imageUrl: string;
  productUrl: string;
  sizeChart: SizeChart;
}

export const GARMENTS: Garment[] = [
  {
    id: "uniqlo_crew_tee",
    name: "Uniqlo Crew Neck T-Shirt",
    brand: "Uniqlo",
    category: "top",
    fit: "regular",
    imageUrl:
      "https://image.uniqlo.com/UQ/ST3/us/imagesgoods/422992/item/usgoods_38_422992_3x4.jpg",
    productUrl: "https://www.uniqlo.com/us/en/products/E422992-000/00",
    sizeChart: {
      XS: { chest_cm: [82, 88], shoulder_cm: [41, 43] },
      S: { chest_cm: [88, 96], shoulder_cm: [43, 45] },
      M: { chest_cm: [96, 104], shoulder_cm: [45, 47] },
      L: { chest_cm: [104, 112], shoulder_cm: [47, 49] },
      XL: { chest_cm: [112, 120], shoulder_cm: [49, 52] },
    },
  },
  {
    id: "uniqlo_oxford_slim",
    name: "Uniqlo Unisex Oxford Slim Shirt",
    brand: "Uniqlo",
    category: "top",
    fit: "slim",
    imageUrl:
      "https://image.uniqlo.com/UQ/ST3/us/imagesgoods/456630/item/usgoods_64_456630_3x4.jpg",
    productUrl: "https://www.uniqlo.com/us/en/products/E456630-000/00",
    sizeChart: {
      XS: { chest_cm: [78, 85], shoulder_cm: [39, 42] },
      S: { chest_cm: [85, 92], shoulder_cm: [42, 44] },
      M: { chest_cm: [92, 99], shoulder_cm: [44, 46] },
      L: { chest_cm: [99, 106], shoulder_cm: [46, 48] },
      XL: { chest_cm: [106, 113], shoulder_cm: [48, 51] },
    },
  },
  {
    id: "charcoal_boxy_tee",
    name: "Charcoal Boxy Heavyweight Tee",
    brand: "Charcoal",
    category: "top",
    fit: "oversized",
    imageUrl: "https://m.media-amazon.com/images/I/51-2xQLzFCL._AC_SL1335_.jpg",
    productUrl: "https://www.amazon.com/dp/B0GG3KCL68",
    sizeChart: {
      XS: { chest_cm: [84, 92], shoulder_cm: [40, 44] },
      S: { chest_cm: [90, 98], shoulder_cm: [43, 47] },
      M: { chest_cm: [96, 104], shoulder_cm: [46, 50] },
      L: { chest_cm: [102, 110], shoulder_cm: [49, 53] },
      XL: { chest_cm: [108, 116], shoulder_cm: [52, 56] },
    },
  },
];

/**
 * Map a recommended item to a curated garment to size against. For the demo we
 * only size tops; a slim/oxford/button item maps to the slim chart, an
 * oversized/boxy one to the boxy chart, otherwise the regular crew tee.
 */
export function pickGarmentFor(item: {
  name?: string;
  category?: string;
}): Garment {
  const text = `${item.name ?? ""} ${item.category ?? ""}`.toLowerCase();
  if (/oxford|button|dress shirt|slim/.test(text))
    return GARMENTS.find((g) => g.fit === "slim")!;
  if (/oversized|boxy|relaxed/.test(text))
    return GARMENTS.find((g) => g.fit === "oversized")!;
  return GARMENTS.find((g) => g.fit === "regular")!;
}
