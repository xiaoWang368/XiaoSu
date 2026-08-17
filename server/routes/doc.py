"""
文档查看页:GET /doc/{doc_id}?chunk={n} 返回自包含 HTML。

引用链接 `/doc/{doc_id}?chunk={n}` 直接点开本页(IM / Web 共用,不依赖前端 app):
  - PDF      → pdf.js(CDN)加载 MinIO 原文件,用 chunk 文本全文搜索高亮
  - md/txt/docx → 渲染 PG 文本,对 chunk n 整段 `<mark>` 高亮
"""

from __future__ import annotations

import html
import json
from typing import List

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from config.minio_config import minio_config
from processor.db import get_chunks, get_document

router = APIRouter()


def _minio_url(doc_id: str, name: str) -> str:
    endpoint = minio_config.endpoint  # 如 localhost:9000(MinIO 已设公开读)
    base = endpoint if endpoint.startswith("http") else f"http://{endpoint}"
    return f"{base}/{minio_config.bucket_name}/{doc_id}/{name}"


def _text_viewer(doc: dict, chunks: List[dict], chunk_idx: int) -> str:
    """md/txt/docx:按 chunk 顺序渲染,目标 chunk 高亮。"""
    blocks = []
    for i, ch in enumerate(chunks):
        text = html.escape(str(ch.get("text", "")))
        cls = "chunk highlight" if i == chunk_idx else "chunk"
        blocks.append(f'<div class="{cls}"><pre>{text}</pre></div>')
    name = html.escape(str(doc.get("name", "")))
    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{name}</title><style>
 body{{font-family:-apple-system,'PingFang SC','Microsoft YaHei',sans-serif;margin:0;background:#f4f5f7;color:#1a1a1a}}
 .bar{{position:sticky;top:0;background:#fff;border-bottom:1px solid #e5e7eb;padding:12px 20px;font-size:14px}}
 .bar b{{color:#2563eb}}
 .wrap{{max-width:760px;margin:0 auto;padding:16px}}
 .chunk{{background:#fff;border:1px solid #e5e7eb;border-radius:8px;margin:10px 0;padding:12px 16px}}
 .chunk pre{{white-space:pre-wrap;font-family:inherit;margin:0;font-size:14px;line-height:1.7}}
 .chunk.highlight{{border-color:#f59e0b;box-shadow:0 0 0 2px #fde68a}}
 .chunk.highlight pre{{background:#fef3c7}}
</style></head><body>
<div class="bar">📄 <b>{name}</b> · 定位到第 {chunk_idx + 1} 段 · <a href="/api/docs">返回</a></div>
<div class="wrap">{''.join(blocks)}</div>
</body></html>"""


def _pdf_viewer(doc: dict, chunks: List[dict], chunk_idx: int) -> str:
    """PDF:pdf.js 加载 MinIO 原文件,文本搜索 chunk 并高亮。"""
    pdf_url = _minio_url(doc["id"], doc["name"])
    query = str(chunks[chunk_idx].get("text", "")) if 0 <= chunk_idx < len(chunks) else ""
    name = html.escape(str(doc.get("name", "")))
    url_json = json.dumps(pdf_url, ensure_ascii=False)
    query_json = json.dumps(query[:50], ensure_ascii=False)  # 搜索前 50 字即可定位
    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{name}</title><style>
 body{{font-family:-apple-system,'PingFang SC','Microsoft YaHei',sans-serif;margin:0;background:#f4f5f7;color:#1a1a1a}}
 .bar{{position:sticky;top:0;background:#fff;border-bottom:1px solid #e5e7eb;padding:12px 20px;font-size:14px}}
 .bar b{{color:#2563eb}}
 .wrap{{max-width:900px;margin:0 auto;padding:16px}}
 .page{{position:relative;margin:10px auto;box-shadow:0 1px 6px rgba(0,0,0,.15)}}
 .page canvas{{display:block;width:100%;height:auto}}
 .page .textLayer{{position:absolute;top:0;left:0;right:0;bottom:0;overflow:hidden;line-height:1;opacity:.001}}
 .page .textLayer span.hl{{background:#fde68a;opacity:1;color:#1a1a1a}}
 .nofind{{color:#dc2626;padding:12px}}
 .status{{color:#6b7280;padding:8px 12px;font-size:13px}}
</style></head><body>
<div class="bar">📄 <b>{name}</b> · PDF 原文 · <a href="/api/docs">返回</a></div>
<div class="status" id="status">正在加载 PDF…</div>
<div class="wrap" id="wrap"></div>
<script src="/static/pdfjs/pdf.min.js"></script>
<script>
pdfjsLib.GlobalWorkerOptions.workerSrc = '/static/pdfjs/pdf.worker.min.js';
const PDF_URL = {url_json};
const QUERY = {query_json};
// 归一化:去掉 markdown 标题#/加粗等标记,压缩空白,便于和 PDF 文本层比对
const norm = (s) => (s || '').replace(/^#+\s*/gm, '').replace(/[*_`~]/g, '').replace(/\s+/g, ' ').trim();
const NQUERY = norm(QUERY);
const NKEY = NQUERY.slice(0, 20);
(async () => {{
  const wrap = document.getElementById('wrap');
  const status = document.getElementById('status');
  let pdf;
  try {{ pdf = await pdfjsLib.getDocument({{url: PDF_URL, cMapUrl: '/static/pdfjs/cmaps/', cMapPacked: true}}).promise; }}
  catch(e) {{ status.textContent = 'PDF 加载失败:' + e.message; return; }}
  status.textContent = '共 ' + pdf.numPages + ' 页';
  let foundPage = -1;
  // 先定位包含 QUERY 的页
  for (let p = 1; p <= pdf.numPages; p++) {{
    const page = await pdf.getPage(p);
    const tc = await page.getTextContent();
    if (foundPage < 0 && NKEY && norm(tc.items.map(i => i.str).join(' ')).includes(NKEY)) foundPage = p;
  }}
  for (let p = 1; p <= pdf.numPages; p++) {{
    const page = await pdf.getPage(p);
    const vp = page.getViewport({{scale: 1.3}});
    const div = document.createElement('div');
    div.className = 'page';
    div.style.width = vp.width + 'px';
    div.style.height = vp.height + 'px';
    const canvas = document.createElement('canvas');
    canvas.width = vp.width; canvas.height = vp.height;
    div.appendChild(canvas);
    wrap.appendChild(div);
    await page.render({{canvasContext: canvas.getContext('2d'), viewport: vp}}).promise;
    if (p === foundPage && NQUERY) {{
      try {{
        const tlDiv = document.createElement('div');
        tlDiv.className = 'textLayer';
        tlDiv.style.width = vp.width + 'px';
        tlDiv.style.height = vp.height + 'px';
        div.appendChild(tlDiv);
        const tl = pdfjsLib.renderTextLayer({{
          textContentSource: await page.getTextContent(),
          container: tlDiv,
          viewport: vp,
        }});
        await tl.promise;
        tlDiv.querySelectorAll('span').forEach(s => {{
          const st = norm(s.textContent);
          if (st.length >= 2 && NQUERY.includes(st)) s.classList.add('hl');
        }});
        status.textContent = '已定位到第 ' + foundPage + ' 页(高亮为引用片段)';
      }} catch(e) {{ status.textContent = '高亮渲染失败(仅显示 PDF):' + e.message; }}
      tlDiv.scrollIntoView({{behavior:'smooth'}});
    }}
  }}
  if (foundPage < 0 && NQUERY) {{
    const d = document.createElement('div');
    d.className = 'nofind';
    d.textContent = '未在 PDF 文本层定位到该段(可能为扫描件,已显示整篇)。';
    wrap.appendChild(d);
  }}
}})();
</script>
</body></html>"""


@router.get("/doc/{doc_id}", response_class=HTMLResponse)
def doc_viewer(doc_id: str, chunk: int = 0):
    doc = get_document(doc_id)
    if not doc:
        return HTMLResponse(
            "<h3>文档不存在或已被更新</h3><p><a href='/api/docs'>返回文档列表</a></p>", status_code=404
        )
    chunks = get_chunks(doc_id)
    chunk_idx = max(0, min(chunk, max(0, len(chunks) - 1)))
    ext = str(doc.get("ext", "")).lower()
    if ext == ".pdf":
        return HTMLResponse(_pdf_viewer(doc, chunks, chunk_idx))
    return HTMLResponse(_text_viewer(doc, chunks, chunk_idx))
