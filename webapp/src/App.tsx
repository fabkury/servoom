import { useEffect, useMemo, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import SparkMD5 from 'spark-md5';
import JSZip from 'jszip';
import './App.css';
import type { GalleryInfo, Session, UserSummary } from './lib/divoomApi';
import {
  downloadBinary,
  fetchCategoryFiles,
  fetchUserGallery,
  login,
  searchUsers,
} from './lib/divoomApi';
import { PyodideDecoder, type DecodedBean } from './lib/pyodideDecoder';
import logger from './lib/logger';

interface DecodeState {
  item: GalleryInfo;
  raw: Uint8Array;
  bean: DecodedBean;
}

const DEFAULT_CATEGORY = 18;
const PAGE_SIZE = 30;
const API_BATCH_LIMIT = 30;
const MAX_ITEMS = 1000;
const HASH_TOOLTIP = 'Only select "Already hashed" if you know what an MD5 hash is. Otherwise, just enter your password.';

class CancelledError extends Error {
  constructor() {
    super('Operation cancelled');
    this.name = 'CancelledError';
  }
}

type FetchContext =
  | { type: 'category'; categoryId: number; start: number; count: number }
  | { type: 'user'; userId: number; nickName: string; start: number; count: number };

type ZipOptionKey = 'webp' | 'gif' | 'dat';

function formatEpoch(epoch: number): string {
  if (!epoch) return '—';
  return new Date(epoch * 1000).toLocaleString();
}

function formatNumber(value: number | undefined): string {
  if (value === undefined) return '—';
  return value.toLocaleString();
}

function safeName(item: GalleryInfo): string {
  return item.FileName?.replace(/[^a-z0-9_\-]+/gi, '_') || String(item.GalleryId);
}

function interpretFileSizeFlag(flag?: number): string {
  switch (flag) {
    case 1:
      return '16 px';
    case 2:
      return '32 px';
    case 4:
      return '64 px';
    case 16:
      return '128 px';
    case 32:
      return '256 px';
    default:
      return '—';
  }
}

function sanitizeSegment(value: string): string {
  const cleaned = value
    .replace(/[<>:"/\\|?*\x00-\x1F]/g, '_')
    .replace(/\s+/g, '_')
    .replace(/_+/g, '_')
    .replace(/^\.+|\.+$/g, '')
    .replace(/^_+|_+$/g, '');
  return cleaned || 'untitled';
}

function blobDownload(data: Uint8Array, filename: string) {
  const buffer = new ArrayBuffer(data.length);
  new Uint8Array(buffer).set(data);
  const blob = new Blob([buffer]);
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

function rgbToRgba(frame: Uint8Array, width: number, height: number): ImageData {
  const rgba = new Uint8ClampedArray(width * height * 4);
  let src = 0;
  for (let i = 0; i < rgba.length; i += 4) {
    rgba[i] = frame[src++];
    rgba[i + 1] = frame[src++];
    rgba[i + 2] = frame[src++];
    rgba[i + 3] = 255;
  }
  return new ImageData(rgba, width, height);
}

function AnimationPreview({ bean, scale }: { bean: DecodedBean; scale: number }) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const width = bean.columnCount * 16;
  const height = bean.rowCount * 16;
  const imageFrames = useMemo(
    () => bean.frames.map((frame) => rgbToRgba(frame, width, height)),
    [bean.frames, width, height],
  );

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    canvas.width = width * scale;
    canvas.height = height * scale;
  }, [width, height, scale]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || imageFrames.length === 0) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.imageSmoothingEnabled = false;

    const offscreen = document.createElement('canvas');
    offscreen.width = width;
    offscreen.height = height;
    const offCtx = offscreen.getContext('2d');
    if (!offCtx) return;
    offCtx.imageSmoothingEnabled = false;

    let frameIndex = 0;
    let timeoutId: number;

    const render = () => {
      offCtx.putImageData(imageFrames[frameIndex], 0, 0);
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(offscreen, 0, 0, canvas.width, canvas.height);
      frameIndex = (frameIndex + 1) % imageFrames.length;
      timeoutId = window.setTimeout(render, bean.speed || 40);
    };

    render();
    return () => {
      window.clearTimeout(timeoutId);
    };
  }, [bean.speed, imageFrames, width, height, scale]);

  return <canvas ref={canvasRef} className="preview-canvas" />;
}

const CATEGORY_OPTIONS: Array<{ value: number; label: string }> = [
  { value: 0, label: 'NEW' },
  { value: 1, label: 'DEFAULT' },
  { value: 3, label: 'CHARACTER' },
  { value: 4, label: 'EMOJI' },
  { value: 5, label: 'DAILY' },
  { value: 6, label: 'NATURE' },
  { value: 7, label: 'SYMBOL' },
  { value: 8, label: 'PATTERN' },
  { value: 9, label: 'CREATIVE' },
  { value: 12, label: 'PHOTO' },
  { value: 14, label: 'TOP' },
  { value: 15, label: 'GADGET' },
  { value: 16, label: 'BUSINESS' },
  { value: 17, label: 'FESTIVAL' },
  { value: 18, label: 'RECOMMEND' },
  { value: 20, label: 'FOLLOW' },
  { value: 30, label: 'CURRENT_EVENT' },
  { value: 31, label: 'PLANT' },
  { value: 32, label: 'ANIMAL' },
  { value: 33, label: 'PERSON' },
  { value: 34, label: 'EMOJI_2' },
  { value: 35, label: 'FOOD' },
];

function App() {
  const decoder = useMemo(() => new PyodideDecoder(), []);
  const downloadCache = useRef<Map<number, Uint8Array>>(new Map());
  const decodedCache = useRef<Map<number, DecodedBean>>(new Map());

  const [session, setSession] = useState<Session | null>(null);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [passwordIsMd5, setPasswordIsMd5] = useState(false);
  const [loginError, setLoginError] = useState<string | null>(null);

  const [categoryId, setCategoryId] = useState(DEFAULT_CATEGORY);
  const [mode, setMode] = useState<'category' | 'user'>('category');
  const [range, setRange] = useState({ start: 1, count: 30 });

  const [items, setItems] = useState<GalleryInfo[]>([]);
  const [itemsLabel, setItemsLabel] = useState<string>('No dataset loaded yet.');
  const [currentPage, setCurrentPage] = useState(0);
  const [selectionMap, setSelectionMap] = useState<Map<number, boolean>>(new Map());
  const [fetchContext, setFetchContext] = useState<FetchContext | null>(null);

  const [userQuery, setUserQuery] = useState('');
  const [userResults, setUserResults] = useState<UserSummary[]>([]);
  const [selectedUser, setSelectedUser] = useState<UserSummary | null>(null);
  const [searchingUsers, setSearchingUsers] = useState(false);

  const [itemsLoading, setItemsLoading] = useState(false);
  const [decodeState, setDecodeState] = useState<DecodeState | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isZipping, setIsZipping] = useState(false);
  const [zipOptions, setZipOptions] = useState<Record<ZipOptionKey, boolean>>({
    webp: true,
    gif: true,
    dat: true,
  });
  const [zipStatus, setZipStatus] = useState<string | null>(null);
  const [zipCacheMeta, setZipCacheMeta] = useState<{ filename: string } | null>(null);
  const [decodingItemId, setDecodingItemId] = useState<number | null>(null);
  const zipCacheRef = useRef<{ url: string; filename: string } | null>(null);

  const paginatedItems = useMemo(() => {
    const start = currentPage * PAGE_SIZE;
    return items.slice(start, start + PAGE_SIZE);
  }, [items, currentPage]);

  const totalPages = Math.max(1, Math.ceil(items.length / PAGE_SIZE));
  const normalizedRange = useMemo(() => {
    const start = Number.isFinite(range.start) ? Math.max(1, Math.floor(range.start)) : 1;
    const count =
      Number.isFinite(range.count) && range.count > 0 ?
        Math.min(MAX_ITEMS, Math.floor(range.count)) :
        1;
    return { start, count, end: start + count - 1 };
  }, [range]);
  const cancelRef = useRef(false);

  const selectedItems = useMemo(
    () => items.filter((item) => selectionMap.get(item.GalleryId)),
    [items, selectionMap],
  );
  const selectionCount = selectedItems.length;
  const currentPageSelected = paginatedItems.filter((item) => selectionMap.get(item.GalleryId)).length;
  const pageHasItems = paginatedItems.length > 0;
  const zipTypesSelected = zipOptions.webp || zipOptions.gif || zipOptions.dat;
  const selectedZipFormats = Object.entries(zipOptions)
    .filter(([, enabled]) => enabled)
    .map(([key]) => key.toUpperCase());
  const decodingLocked = decodingItemId !== null;
  useEffect(() => {
    return () => {
      if (zipCacheRef.current) {
        URL.revokeObjectURL(zipCacheRef.current.url);
        zipCacheRef.current = null;
      }
    };
  }, []);

  const handleSelectCurrentPage = () => {
    if (!pageHasItems) return;
    setSelectionMap((prev) => {
      const next = new Map(prev);
      paginatedItems.forEach((item) => next.set(item.GalleryId, true));
      return next;
    });
  };

  const handleUnselectCurrentPage = () => {
    if (!pageHasItems) return;
    setSelectionMap((prev) => {
      const next = new Map(prev);
      paginatedItems.forEach((item) => next.delete(item.GalleryId));
      return next;
    });
  };

  const handleCancelFetch = () => {
    if (!itemsLoading) return;
    cancelRef.current = true;
    setStatus('Cancelling current fetch…');
    setItemsLoading(false);
  };

  const handleZipOptionToggle = (key: ZipOptionKey) => {
    setZipOptions((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const renderPaginationControls = (className: string) => (
    <div className={className}>
      <div>
        <strong>{itemsLabel}</strong>
        <div>
          Page {currentPage + 1} / {totalPages} · {items.length} items · {selectionCount} selected
        </div>
      </div>
      <div className="results-tools">
        <button onClick={handleSelectCurrentPage} disabled={!pageHasItems}>
          Select all (page)
        </button>
        <button onClick={handleUnselectCurrentPage} disabled={!currentPageSelected}>
          Unselect all (page)
        </button>
        <div className="actions">
          <button onClick={() => setCurrentPage((p) => Math.max(0, p - 1))} disabled={currentPage === 0}>
            Previous
          </button>
          <button
            onClick={() => setCurrentPage((p) => Math.min(totalPages - 1, p + 1))}
            disabled={currentPage >= totalPages - 1}
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );

  const handleLogin = async (event: FormEvent) => {
    event.preventDefault();
    setLoginError(null);
    setError(null);
    try {
      logger.info('Login attempt', { email, hashed: passwordIsMd5 });
      const md5 = passwordIsMd5 ? password : SparkMD5.hash(password);
      const result = await login(email, md5);
      setSession(result);
      logger.info('Login success', { userId: result.userId });
    } catch (err) {
      setLoginError((err as Error).message);
      logger.error('Login failed', err);
    }
  };

  const handleLogout = () => {
    downloadCache.current.clear();
    decodedCache.current.clear();
    setSession(null);
    setLoginError(null);
    setItems([]);
    setItemsLabel('No dataset loaded yet.');
    setCurrentPage(0);
    setSelectionMap(new Map());
    setFetchContext(null);
    setDecodeState(null);
    setStatus(null);
    setError(null);
    setUserResults([]);
    setSelectedUser(null);
    setSearchingUsers(false);
  };

  const resetDataset = (list: GalleryInfo[], label: string, context: FetchContext | null) => {
    const trimmed = list.slice(0, MAX_ITEMS);
    setItems(trimmed);
    setItemsLabel(label);
    setCurrentPage(0);
    setSelectionMap(new Map());
    setDecodeState(null);
    setFetchContext(context);
  };

  const fetchInBatches = async (
    start: number,
    count: number,
    loader: (chunkStart: number, chunkEnd: number) => Promise<GalleryInfo[]>,
    options?: {
      onProgress?: (info: { chunk: number; start: number; end: number }) => void;
      isCancelled?: () => boolean;
    },
  ): Promise<GalleryInfo[]> => {
    const targetCount = Math.min(MAX_ITEMS, count);
    const collected: GalleryInfo[] = [];
    const seen = new Set<string | number>();
    let cursor = start;
    let remaining = targetCount;
    let attempts = 0;
    const maxAttempts = Math.ceil(targetCount / API_BATCH_LIMIT) + 5;
    let chunkIndex = 0;

    while (remaining > 0 && attempts < maxAttempts) {
      if (options?.isCancelled?.()) {
        throw new CancelledError();
      }
      attempts += 1;
      const chunkSize = Math.min(API_BATCH_LIMIT, remaining);
      const chunkEnd = cursor + chunkSize - 1;
      chunkIndex += 1;
      options?.onProgress?.({ chunk: chunkIndex, start: cursor, end: chunkEnd });
      const before = collected.length;
      const batch = await loader(cursor, chunkEnd);

      for (const item of batch) {
        const key =
          item.GalleryId ??
          (typeof item.FileId === 'string' ? item.FileId : `${item.FileName ?? ''}-${item.Date ?? 0}`);
        if (seen.has(key)) continue;
        seen.add(key);
        collected.push(item);
      }

      if (batch.length === 0) break;
      if (collected.length === before) break; // no new items added
      if (collected.length >= targetCount) break;

      cursor += chunkSize;
      remaining = targetCount - collected.length;
    }

    return collected.slice(0, targetCount);
  };

  const handleFetchCategory = async () => {
    if (!session) return;
    setItemsLoading(true);
    setError(null);
    const { start, count, end } = normalizedRange;
    cancelRef.current = false;
    setStatus('Starting category fetch…');
    let clearStatus = true;
    try {
      logger.info('Fetching category', { categoryId, start, count });
      const files = await fetchInBatches(
        start,
        count,
        (chunkStart, chunkEnd) =>
          fetchCategoryFiles(session, {
            classify: categoryId,
            start: chunkStart,
            end: chunkEnd,
          }),
        {
          onProgress: ({ chunk, start: chunkStart, end: chunkEnd }) => {
            setStatus(`Fetching category batch ${chunk}: #${chunkStart}–#${chunkEnd}`);
          },
          isCancelled: () => cancelRef.current,
        },
      );
      const label = `Category ${categoryId} · #${start}–#${end} (${files.length} items)`;
      resetDataset(files, label, { type: 'category', categoryId, start, count });
    } catch (err) {
      if (err instanceof CancelledError) {
        setError(null);
        setStatus('Category fetch cancelled');
        logger.info('Category fetch cancelled');
        clearStatus = false;
      } else {
        setError((err as Error).message);
        logger.error('Category fetch failed', err);
      }
    } finally {
      cancelRef.current = false;
      if (clearStatus) {
        setStatus(null);
      }
      setItemsLoading(false);
    }
  };

  const handleSearchUsers = async () => {
    if (!session || !userQuery.trim()) return;
    setSearchingUsers(true);
    setError(null);
    try {
      logger.info('Searching users', { query: userQuery });
      const results = await searchUsers(session, userQuery.trim());
      setUserResults(results);
      if (!results.length) {
        setSelectedUser(null);
      }
    } catch (err) {
      setError((err as Error).message);
      logger.error('User search failed', err);
    } finally {
      setSearchingUsers(false);
    }
  };

  const handleFetchUserGallery = async () => {
    if (!session || !selectedUser) return;
    setItemsLoading(true);
    setError(null);
    const { start, count, end } = normalizedRange;
    cancelRef.current = false;
    setStatus('Starting user fetch…');
    let clearStatus = true;
    try {
      logger.info('Fetching user gallery', { userId: selectedUser.UserId, start, count });
      const files = await fetchInBatches(
        start,
        count,
        (chunkStart, chunkEnd) => fetchUserGallery(session, selectedUser.UserId, chunkStart, chunkEnd),
        {
          onProgress: ({ chunk, start: chunkStart, end: chunkEnd }) => {
            setStatus(`Fetching user batch ${chunk}: #${chunkStart}–#${chunkEnd}`);
          },
          isCancelled: () => cancelRef.current,
        },
      );
      const label = `User ${selectedUser.NickName} (#${selectedUser.UserId}) · #${start}–#${end} (${files.length} items)`;
      resetDataset(files, label, {
        type: 'user',
        userId: selectedUser.UserId,
        nickName: selectedUser.NickName,
        start,
        count,
      });
    } catch (err) {
      if (err instanceof CancelledError) {
        setError(null);
        setStatus('User fetch cancelled');
        logger.info('User fetch cancelled');
        clearStatus = false;
      } else {
        setError((err as Error).message);
        logger.error('User gallery fetch failed', err);
      }
    } finally {
      cancelRef.current = false;
      if (clearStatus) {
        setStatus(null);
      }
      setItemsLoading(false);
    }
  };

  const fetchRaw = async (item: GalleryInfo): Promise<Uint8Array> => {
    const cached = downloadCache.current.get(item.GalleryId);
    if (cached) {
      logger.info('Using cached binary', { galleryId: item.GalleryId });
      return cached;
    }
    setStatus('Downloading binary payload…');
    logger.info('Downloading binary', { galleryId: item.GalleryId, fileId: item.FileId });
    const data = await downloadBinary(item.FileId);
    downloadCache.current.set(item.GalleryId, data);
    setStatus(null);
    logger.info('Binary downloaded', { galleryId: item.GalleryId, bytes: data.length });
    return data;
  };

  const handleDecode = async (item: GalleryInfo) => {
    if (decodingLocked) return;
    setDecodingItemId(item.GalleryId);
    setError(null);
    try {
      logger.info('Decode requested', { galleryId: item.GalleryId });
      const raw = await fetchRaw(item);
      setStatus('Initializing decoder…');
      let bean = decodedCache.current.get(item.GalleryId);
      if (!bean) {
        bean = await decoder.decode(raw);
        decodedCache.current.set(item.GalleryId, bean);
      }
      setDecodeState({ item, raw, bean });
      setStatus(null);
      logger.info('Decode success', {
        galleryId: item.GalleryId,
        frames: bean.totalFrames,
        speed: bean.speed,
        size: `${bean.columnCount * 16}x${bean.rowCount * 16}`,
      });
    } catch (err) {
      setStatus(null);
      setError((err as Error).message);
      logger.error('Decode failed', err);
    } finally {
      setDecodingItemId(null);
    }
  };

  const handleDownloadRaw = async (item: GalleryInfo) => {
    try {
      const raw = await fetchRaw(item);
      blobDownload(raw, `${safeName(item)}_${item.GalleryId}.dat`);
      setStatus(null);
      logger.info('Raw download triggered', { galleryId: item.GalleryId });
    } catch (err) {
      setError((err as Error).message);
      logger.error('Raw download failed', err);
    }
  };

  const handleDownloadWebp = () => {
    if (!decodeState) return;
    blobDownload(
      decodeState.bean.webp,
      `${safeName(decodeState.item)}_${decodeState.item.GalleryId}.webp`,
    );
    logger.info('WebP download triggered', { galleryId: decodeState.item.GalleryId });
  };

  const handleDownloadGif = () => {
    if (!decodeState) return;
    blobDownload(
      decodeState.bean.gif,
      `${safeName(decodeState.item)}_${decodeState.item.GalleryId}.gif`,
    );
    logger.info('GIF download triggered', { galleryId: decodeState.item.GalleryId });
  };

  const handleCheckboxChange = (galleryId: number, checked: boolean) => {
    setSelectionMap((prev) => {
      const next = new Map(prev);
      if (checked) {
        next.set(galleryId, true);
      } else {
        next.delete(galleryId);
      }
      return next;
    });
  };

  const handleZipDownload = async () => {
    if (!selectionCount) return;
    if (!zipTypesSelected) {
      setError('Select at least one file type to export.');
      return;
    }
    if (zipCacheRef.current) {
      URL.revokeObjectURL(zipCacheRef.current.url);
      zipCacheRef.current = null;
      setZipCacheMeta(null);
    }
    setIsZipping(true);
    setError(null);
    setZipStatus('Initializing ZIP export…');
    try {
      logger.info('Preparing ZIP', { selectionCount });
      const zip = new JSZip();
      const folderSegments =
        fetchContext?.type === 'category'
          ? [
              'servoom',
              `category-${fetchContext.categoryId}`,
              `start-${fetchContext.start}-count-${fetchContext.count}`,
            ]
          : fetchContext?.type === 'user'
            ? [
                'servoom',
                `${fetchContext.nickName}-${fetchContext.userId}`,
                `start-${fetchContext.start}-count-${fetchContext.count}`,
              ]
            : ['servoom', 'selection'];
      const basePath = folderSegments.map(sanitizeSegment).join('/');
      const datFolder = zipOptions.dat ? zip.folder(`${basePath}/DAT`) : null;
      const webpFolder = zipOptions.webp ? zip.folder(`${basePath}/WebP`) : null;
      const gifFolder = zipOptions.gif ? zip.folder(`${basePath}/GIF`) : null;
      if ((zipOptions.dat && !datFolder) || (zipOptions.webp && !webpFolder) || (zipOptions.gif && !gifFolder)) {
        throw new Error('Failed to create ZIP folders');
      }
      for (let i = 0; i < selectedItems.length; i += 1) {
        const item = selectedItems[i];
        const progressLabel = item.FileName || `Gallery ${item.GalleryId}`;
        setZipStatus(`Zipping ${i + 1}/${selectionCount}: ${progressLabel}`);
        const raw = await fetchRaw(item);
        if (zipOptions.dat && datFolder) {
          datFolder.file(`${safeName(item)}_${item.GalleryId}.dat`, raw);
        }
        let bean = decodedCache.current.get(item.GalleryId);
        if (!bean) {
          bean = await decoder.decode(raw);
          decodedCache.current.set(item.GalleryId, bean);
        }
        if (zipOptions.webp && webpFolder) {
          webpFolder.file(`${safeName(item)}_${item.GalleryId}.webp`, bean.webp);
        }
        if (zipOptions.gif && gifFolder) {
          gifFolder.file(`${safeName(item)}_${item.GalleryId}.gif`, bean.gif);
        }
      }
      setZipStatus('Finalizing ZIP archive…');
      const blob = await zip.generateAsync({ type: 'blob' });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      const archiveLabel =
        fetchContext?.type === 'category'
          ? `category-${fetchContext.categoryId}`
          : fetchContext?.type === 'user'
            ? `user-${sanitizeSegment(fetchContext.nickName)}-${fetchContext.userId}`
            : 'selection';
      const filename = `${archiveLabel}-${Date.now()}.zip`;
      anchor.download = filename;
      anchor.click();
      zipCacheRef.current = { url, filename };
      setZipCacheMeta({ filename });
      logger.info('ZIP download ready');
      setZipStatus('ZIP download ready');
    } catch (err) {
      setError((err as Error).message);
      logger.error('ZIP creation failed', err);
      setZipStatus('ZIP creation failed');
    } finally {
      if (!selectionCount) {
        setZipStatus(null);
      }
      setIsZipping(false);
    }
  };

  const handleDownloadCachedZip = () => {
    const cache = zipCacheRef.current;
    if (!cache) return;
    const anchor = document.createElement('a');
    anchor.href = cache.url;
    anchor.download = cache.filename;
    anchor.click();
    logger.info('ZIP redownload triggered', { filename: cache.filename });
  };

  const scale =
    decodeState ?
      Math.max(1, Math.floor(256 / Math.max(decodeState.bean.columnCount * 16, decodeState.bean.rowCount * 16))) :
      1;

  return (
    <div className="app-shell">
      <header>
        <h1>servoom web</h1>
        <p>Divoom Cloud data export tool</p>
      </header>

      <section className="panel">
        <h2>1. Sign in</h2>
        {session ? (
          <div className="status success login-status">
            <span>Logged in as {session.email}</span>
            <button type="button" onClick={handleLogout}>
              Log out
            </button>
          </div>
        ) : (
          <form className="grid-form" onSubmit={handleLogin}>
            <label>
              Email
              <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
            </label>
            <label title={HASH_TOOLTIP}>
              Password or MD5 hash
              <input
                type="text"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                title={HASH_TOOLTIP}
              />
            </label>
            <label className="checkbox" title={HASH_TOOLTIP}>
              <input
                type="checkbox"
                checked={passwordIsMd5}
                onChange={(e) => setPasswordIsMd5(e.target.checked)}
                title={HASH_TOOLTIP}
              />
              Password is already hashed
            </label>
            <button type="submit">Sign in to Divoom Cloud</button>
            {loginError && <div className="status error">{loginError}</div>}
          </form>
        )}
      </section>

      <section className="panel">
        <h2>2. Choose source</h2>
        <div className="mode-toggle">
          <button
            type="button"
            className={mode === 'category' ? 'active' : ''}
            onClick={() => setMode('category')}
          >
            By category
          </button>
          <button
            type="button"
            className={mode === 'user' ? 'active' : ''}
            onClick={() => setMode('user')}
          >
            By user
          </button>
        </div>

        {mode === 'category' && (
          <div className="mode-panel">
            <div className="grid-form">
              <label>
                Category
                <select
                  value={categoryId}
                  onChange={(e) => {
                    const value = Number(e.target.value);
                    setCategoryId(Number.isFinite(value) ? value : DEFAULT_CATEGORY);
                  }}
                >
                  {CATEGORY_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label} ({option.value})
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Start #
                <input
                  type="number"
                  value={range.start}
                  min={1}
                  onChange={(e) =>
                    setRange((prev) => ({
                      ...prev,
                      start: Math.max(1, Number(e.target.value) || 1),
                    }))
                  }
                />
              </label>
              <label>
                Number of items
                <input
                  type="number"
                  value={Number.isFinite(range.count) ? range.count : ''}
                  min={1}
                  onBlur={(e) => {
                    const raw = Number(e.target.value);
                    setRange((prev) => ({
                      ...prev,
                      count: Number.isFinite(raw) && raw > 0 ? Math.min(MAX_ITEMS, Math.floor(raw)) : 1,
                    }));
                  }}
                  onChange={(e) => {
                    const raw = Number(e.target.value);
                    setRange((prev) => ({
                      ...prev,
                      count: Number.isNaN(raw) ? NaN : raw,
                    }));
                  }}
                />
              </label>
              <button
                onClick={handleFetchCategory}
                disabled={!session || itemsLoading}
                title={!session ? "You need to log in first to fetch artworks" : undefined}
              >
                {itemsLoading ? "Loading…" : "Fetch artworks"}
              </button>
            </div>
          </div>
        )}

        {mode === 'user' && (
          <div className="mode-panel">
            <div className="grid-form">
              <label>
                Search users
                <input
                  type="text"
                  value={userQuery}
                  placeholder="nickname fragment"
                  onChange={(e) => setUserQuery(e.target.value)}
                />
              </label>
          <button
            onClick={handleSearchUsers}
            disabled={!session || searchingUsers}
                title={!session ? "You need to log in first to search" : undefined}
              >
                {searchingUsers ? "Searching…" : "Search"}
              </button>
            </div>
            {userResults.length > 0 && (
              <div className="user-results">
                <strong>Results:</strong>
                <ul>
                  {userResults.map((user) => (
                    <li key={user.UserId}>
                      {user.NickName} (#{user.UserId}){' '}
                      <button onClick={() => setSelectedUser(user)}>Select</button>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {selectedUser && (
              <>
                <div className="selected-user">
                  Selected user: <strong>{selectedUser.NickName}</strong> (#{selectedUser.UserId})
                  <button type="button" onClick={() => setSelectedUser(null)}>
                    Clear
                  </button>
                </div>
                <div className="grid-form">
                  <label>
                    Start #
                    <input
                      type="number"
                      value={range.start}
                      min={1}
                      onChange={(e) =>
                        setRange((prev) => ({
                          ...prev,
                          start: Math.max(1, Number(e.target.value) || 1),
                        }))
                      }
                    />
                  </label>
                  <label>
                    Number of items
                    <input
                      type="number"
                      value={Number.isFinite(range.count) ? range.count : ''}
                      min={1}
                      onBlur={(e) => {
                        const raw = Number(e.target.value);
                        setRange((prev) => ({
                          ...prev,
                          count: Number.isFinite(raw) && raw > 0 ? Math.min(MAX_ITEMS, Math.floor(raw)) : 1,
                        }));
                      }}
                      onChange={(e) => {
                        const raw = Number(e.target.value);
                        setRange((prev) => ({
                          ...prev,
                          count: Number.isNaN(raw) ? NaN : raw,
                        }));
                      }}
                    />
                  </label>
                <button
                    onClick={handleFetchUserGallery}
                    disabled={!session || itemsLoading || !selectedUser}
                  >
                    {itemsLoading ? "Loading…" : "Fetch artworks"}
                  </button>
                </div>
              </>
            )}
          </div>
        )}
      </section>

      {(status || error) && (
        <div className="status-stack">
          {status && <div className="status info">{status}</div>}
          {error && <div className="status error">{error}</div>}
        </div>
      )}
      {itemsLoading && (
        <div className="cancel-bar">
          <button type="button" onClick={handleCancelFetch}>
            Cancel current fetch
          </button>
        </div>
      )}

      <section className="panel">
        <h2>3. Results</h2>
        {renderPaginationControls('results-header')}

        {paginatedItems.length ? (
          <>
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Select</th>
                    <th>Name</th>
                    <th>ID</th>
                  <th>Likes</th>
                  <th>Views</th>
                  <th>Uploaded</th>
                  <th>Size</th>
                  <th>Actions</th>
                </tr>
                </thead>
                <tbody>
                  {paginatedItems.map((item) => (
                    <tr key={item.GalleryId}>
                    <td>
                      <input
                        type="checkbox"
                        checked={Boolean(selectionMap.get(item.GalleryId))}
                        onChange={(e) => handleCheckboxChange(item.GalleryId, e.target.checked)}
                      />
                    </td>
                    <td>{item.FileName}</td>
                    <td>{item.GalleryId}</td>
                    <td>{formatNumber(item.LikeCnt)}</td>
                    <td>{formatNumber(item.WatchCnt)}</td>
                    <td>{formatEpoch(item.Date)}</td>
                    <td>{interpretFileSizeFlag(item.FileSize as number)}</td>
                    <td className="actions table-actions">
                      <button onClick={() => handleDecode(item)} disabled={decodingLocked}>
                        {decodingItemId === item.GalleryId ? 'Decoding…' : 'Decode'}
                      </button>
                      <button onClick={() => handleDownloadRaw(item)}>Raw</button>
                    </td>
                  </tr>
                ))}
                </tbody>
              </table>
            </div>
            {renderPaginationControls('results-footer')}
          </>
        ) : (
          <p>No items loaded yet.</p>
        )}
        <div className="preview-panel">
          <h3>Preview &amp; export single artwork</h3>
          {decodeState ? (
            <>
              <div className="decode-meta">
                <div>
                  <strong>{decodeState.item.FileName}</strong>
                  <div>Gallery #{decodeState.item.GalleryId}</div>
                  <div>
                    {decodeState.bean.columnCount * 16} × {decodeState.bean.rowCount * 16} ·{' '}
                    {decodeState.bean.totalFrames} frames @{decodeState.bean.speed} ms
                  </div>
                </div>
                <div className="preview-actions">
                  <button onClick={handleDownloadWebp}>Download WebP</button>
                  <button onClick={handleDownloadGif}>Download GIF</button>
                  <button onClick={() => blobDownload(decodeState.raw, `${decodeState.item.GalleryId}.dat`)}>
                    Download DAT
                  </button>
                </div>
              </div>
              <AnimationPreview bean={decodeState.bean} scale={scale} />
            </>
          ) : (
            <p>No artwork decoded yet. Click “Decode” on any row to preview it here.</p>
          )}
        </div>
      </section>

      <section className="panel">
        <h2>4. Download selection</h2>
        <div className="zip-options">
          <label className="checkbox">
            <input
              type="checkbox"
              checked={zipOptions.webp}
              onChange={() => handleZipOptionToggle('webp')}
            />
            WebP
          </label>
          <label className="checkbox">
            <input type="checkbox" checked={zipOptions.gif} onChange={() => handleZipOptionToggle('gif')} />
            GIF
          </label>
          <label className="checkbox">
            <input type="checkbox" checked={zipOptions.dat} onChange={() => handleZipOptionToggle('dat')} />
            DAT (raw)
          </label>
        </div>
        <div className="zip-bar">
          <div className="zip-summary">
            <div className="zip-message">
              {selectionCount ?
                zipTypesSelected ?
                  `Ready to bundle ${selectionCount} artwork${selectionCount === 1 ? '' : 's'} as ${selectedZipFormats.join(', ')} (max ${MAX_ITEMS}).` :
                  'Enable at least one format above to export.' :
                'Select artworks above to enable ZIP export.'}
            </div>
            {zipStatus && <div className="zip-progress">{zipStatus}</div>}
            {zipCacheMeta && <div className="zip-cache-note">Last ZIP: {zipCacheMeta.filename}</div>}
          </div>
          <div className="zip-buttons">
            <button onClick={handleZipDownload} disabled={!selectionCount || isZipping || !zipTypesSelected}>
              {isZipping ? 'Preparing ZIP…' : 'Build ZIP'}
            </button>
            <button type="button" onClick={handleDownloadCachedZip} disabled={!zipCacheMeta}>
              Download ZIP
            </button>
          </div>
        </div>
      </section>
      <footer className="page-footer">❤️ pixel art, ❤️ pixel artists.</footer>
    </div>
  );
}

export default App;
