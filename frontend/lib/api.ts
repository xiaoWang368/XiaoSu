/** 后端地址：默认走 Next 反代(相对 /api)，可被 NEXT_PUBLIC_API_BASE 覆盖。 */

export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";
