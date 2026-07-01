"""Export artwork metadata to CSV.

Split out of the API client: turning a list of :class:`~servoom.pixel_bean.PixelBean`
metadata records into CSV is a presentation concern, not an API concern. Uses the stdlib
``csv`` module (no pandas).
"""

from __future__ import annotations

import csv
import os
from datetime import datetime
from typing import Dict, List, Optional

from .logging import get_logger

log = get_logger(__name__)

# Raw API key -> human-friendly CSV column header. Column order follows this mapping.
FIELD_MAPPINGS: Dict[str, str] = {
    "IsLike": "Is Like",
    "GalleryId": "Gallery ID",
    "UserId": "User ID",
    "PixelAmbId": "Pixel Amb ID",
    "PixelAmbName": "Pixel Amb Name",
    "UserName": "User Name",
    "UserHeaderId": "User Header ID",
    "Level": "Level",
    "RegionId": "Region ID",
    "CountryISOCode": "Country ISO Code",
    "IsFollow": "Is Follow",
    "LikeUTC": "Like UTC",
    "CommentUTC": "Comment UTC",
    "AtList": "At List",
    "ShareCnt": "Share Count",
    "Content": "Content",
    "FileTagArray": "File Tag Array",
    "PrivateFlag": "Private Flag",
    "CopyrightFlag": "Copyright Flag",
    "IsDel": "Is Deleted",
    "CheckConfirm": "Check Confirm",
    "FileType": "File Type",
    "LikeCnt": "Like Count",
    "WatchCnt": "Watch Count",
    "Classify": "Classify",
    "FillGameScore": "Fill Game Score",
    "OriginalGalleryId": "Original Gallery ID",
    "FileName": "File Name",
    "FileSize": "File Size",
    "HideFlag": "Hide Flag",
    "IsAddNew": "Is Add New",
    "IsAddRecommend": "Is Add Recommend",
    "Date": "Creation",
    "CommentCnt": "Comment Count",
    "FileId": "File ID",
    "MusicFileId": "Music File ID",
    "LayerFileId": "Layer File ID",
    "FileURL": "File URL",
    "FillGameIsFinish": "Fill Game Is Finish",
    "AIFlag": "AI Flag",
}


def _timestamped(filename: str) -> str:
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    stem, ext = os.path.splitext(filename)
    return f"{stem}_{stamp}{ext}"


def _row_from_metadata(metadata: Dict) -> Dict[str, str]:
    row: Dict[str, str] = {}
    for key, header in FIELD_MAPPINGS.items():
        if key not in metadata:
            continue
        value = metadata[key]
        if key == "Date":
            value = datetime.fromtimestamp(value).strftime("%Y-%m-%d %H:%M:%S")
        elif key == "FileSize":
            value = str(value)
        row[header] = value
    return row


def export_artworks_to_csv(
    beans,
    base_filename: str = "artworks",
    output_dir: str = "out",
    include_tags: bool = True,
) -> Dict[str, str]:
    """Write an artworks CSV (and optionally a tags CSV) from PixelBean metadata.

    Returns a mapping ``{"artworks": path[, "tags": path]}``.
    """
    os.makedirs(output_dir, exist_ok=True)

    rows = [_row_from_metadata(bean.metadata) for bean in beans]
    # Columns = mapped headers that appear in at least one row, in FIELD_MAPPINGS order.
    present = {header for row in rows for header in row}
    columns = [h for h in FIELD_MAPPINGS.values() if h in present]

    artworks_path = os.path.join(output_dir, _timestamped(f"{base_filename}.csv"))
    with open(artworks_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns, restval="")
        writer.writeheader()
        writer.writerows(rows)
    log.info("Exported artworks: %s", artworks_path)
    result = {"artworks": artworks_path}

    if include_tags:
        tag_rows = []
        for bean in beans:
            metadata = bean.metadata
            for tag in metadata.get("FileTagArray", []) or []:
                tag_rows.append({
                    "GalleryId": metadata.get("GalleryId"),
                    "Art Name": metadata.get("FileName"),
                    "Tag Name": tag,
                })
        if tag_rows:
            tags_path = os.path.join(output_dir, _timestamped(f"{base_filename}_tags.csv"))
            with open(tags_path, "w", newline="", encoding="utf-8") as fh:
                writer = csv.DictWriter(fh, fieldnames=["GalleryId", "Art Name", "Tag Name"])
                writer.writeheader()
                writer.writerows(tag_rows)
            log.info("Exported tags: %s", tags_path)
            result["tags"] = tags_path

    return result
