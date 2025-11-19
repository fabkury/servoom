export interface Session {
  token: string;
  userId: number;
  email: string;
}

export interface GalleryInfo {
  GalleryId: number;
  FileId: string;
  FileName: string;
  FileType: number;
  FileURL?: string;
  Classify: number;
  Date: number;
  LikeCnt: number;
  WatchCnt: number;
  CommentCnt: number;
  UserName?: string;
  UserId?: number;
  [key: string]: unknown;
}

const RESPECT_HIDE_FLAG = true;

function shouldExcludeHidden(item: GalleryInfo): boolean {
  if (!RESPECT_HIDE_FLAG) {
    return false;
  }
  return Boolean(item.HideFlag); // Treats undefined, null, 0, false as false
}

const API_BASE = 'https://app.divoom-gz.com';
const FILE_BASE = 'https://f.divoom-gz.com';

const DEFAULT_HEADERS = {
  'Content-Type': 'application/json',
  'User-Agent': 'Aurabox/3.1.10 (iPad; iOS 14.8; Scale/2.00)',
};

export type ApiAction = 'login' | 'category' | 'userGallery' | 'search';

export class ApiError extends Error {
  action: ApiAction;
  code: number;

  constructor(action: ApiAction, code: number) {
    super(`${action} failed with ReturnCode ${code}`);
    this.name = 'ApiError';
    this.action = action;
    this.code = code;
  }
}

async function postJson<T>(url: string, body: Record<string, unknown>): Promise<T> {
  const resp = await fetch(url, {
    method: 'POST',
    headers: DEFAULT_HEADERS,
    body: JSON.stringify(body),
  });
  if (!resp.ok) {
    throw new Error(`Request failed with status ${resp.status}`);
  }
  return (await resp.json()) as T;
}

export async function login(email: string, md5Password: string): Promise<Session> {
  const response = await postJson<{
    ReturnCode: number;
    UserId: number;
    Token: string;
  }>(`${API_BASE}/UserLogin`, {
    Email: email,
    Password: md5Password,
  });

  if (response.ReturnCode !== 0) {
    throw new ApiError('login', response.ReturnCode);
  }

  return {
    token: response.Token,
    userId: response.UserId,
    email,
  };
}

export interface CategoryParams {
  classify: number;
  start?: number;
  end?: number;
  fileSizeMask?: number;
  fileType?: number;
  sort?: number;
}

export async function fetchCategoryFiles(
  session: Session,
  params: CategoryParams,
): Promise<GalleryInfo[]> {
  const payload = {
    StartNum: params.start ?? 1,
    EndNum: params.end ?? 100,
    Classify: params.classify,
    FileSize: params.fileSizeMask ?? 31,
    FileType: params.fileType ?? 5,
    FileSort: params.sort ?? 0,
    Version: 12,
    RefreshIndex: 0,
    Token: session.token,
    UserId: session.userId,
  };

  const response = await postJson<{
    ReturnCode: number;
    FileList: GalleryInfo[];
  }>(`${API_BASE}/GetCategoryFileListV2`, payload);

  if (response.ReturnCode !== 0) {
    throw new ApiError('category', response.ReturnCode);
  }
  return (response.FileList ?? []).filter(item => !shouldExcludeHidden(item));
}

export interface UserSummary {
  UserId: number;
  NickName: string;
  UserName?: string;
  FansCnt?: number;
  Score?: number;
}

export async function searchUsers(session: Session, query: string): Promise<UserSummary[]> {
  const payload = {
    Keywords: query,
    Token: session.token,
    UserId: session.userId,
  };

  const response = await postJson<{
    ReturnCode: number;
    UserList: UserSummary[];
  }>(`${API_BASE}/SearchUser`, payload);

  if (response.ReturnCode !== 0) {
    throw new ApiError('search', response.ReturnCode);
  }
  return response.UserList ?? [];
}

export async function fetchUserGallery(
  session: Session,
  userId: number,
  start = 1,
  end = 60,
): Promise<GalleryInfo[]> {
  const payload = {
    StartNum: start,
    EndNum: end,
    Version: 99,
    ShowAllFlag: 1,
    SomeOneUserId: userId,
    FileSize: 0b1 | 0b10 | 0b100 | 0b1000 | 0b10000 | 0b100000,
    RefreshIndex: 0,
    FileSort: 0,
    Token: session.token,
    UserId: session.userId,
  };

  const response = await postJson<{
    ReturnCode: number;
    FileList: GalleryInfo[];
  }>(`${API_BASE}/GetSomeoneListV2`, payload);

  if (response.ReturnCode !== 0) {
    throw new ApiError('userGallery', response.ReturnCode);
  }
  return (response.FileList ?? []).filter(item => !shouldExcludeHidden(item));
}

export async function downloadBinary(fileId: string): Promise<Uint8Array> {
  const normalized = fileId.startsWith('/') ? fileId : `/${fileId}`;
  const resp = await fetch(`${FILE_BASE}${normalized}`);
  if (!resp.ok) {
    throw new Error(`File download failed with status ${resp.status}`);
  }
  const buffer = await resp.arrayBuffer();
  return new Uint8Array(buffer);
}
