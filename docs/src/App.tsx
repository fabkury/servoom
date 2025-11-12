import { useEffect, useMemo, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import SparkMD5 from 'spark-md5';
import JSZip from 'jszip';
import './App.css';
import type { GalleryInfo, Session, UserSummary } from './lib/divoomApi';
import {
  ApiError,
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
const LOCALE_STORAGE_KEY = 'servoom-locale';

type Locale = 'en' | 'es' | 'zh' | 'ja' | 'ru';
type ZipOptionKey = 'webp' | 'gif' | 'dat';

interface Translation {
  header: { title: string; tagline: string; footer: string; languageLabel: string };
  panels: { signIn: string; chooseSource: string; results: string; download: string };
  mode: { category: string; user: string };
  buttons: {
    signIn: string;
    logout: string;
    fetch: string;
    search: string;
    clear: string;
    select: string;
    decode: string;
    decoding: string;
    raw: string;
    buildZip: string;
    downloadZip: string;
    downloadWebp: string;
    downloadGif: string;
    downloadDat: string;
    cancelFetch: string;
    selectPage: string;
    unselectPage: string;
    previousPage: string;
    nextPage: string;
    loading: string;
    searching: string;
  };
  labels: {
    email: string;
    password: string;
    passwordHashed: string;
    category: string;
    start: string;
    count: string;
    searchUsers: string;
    selectedUser: string;
    resultsHeading: string;
    artist: string;
  };
  placeholders: { searchUsers: string };
  tooltips: { hash: string; fetchLogin: string; searchLogin: string };
    messages: {
      noDataset: string;
      noItems: string;
      previewPlaceholder: string;
      unknownArtist: string;
      loggedInAs: (email: string) => string;
    categoryLabel: (categoryId: number, start: number, end: number, count: number) => string;
    userLabel: (nickname: string, userId: number, start: number, end: number, count: number) => string;
    userListEntry: (nickname: string, userId: number) => string;
    previewMeta: (width: number, height: number, frames: number, speed: number) => string;
  };
  table: {
    headers: {
      select: string;
      name: string;
      id: string;
      likes: string;
      views: string;
      uploaded: string;
      size: string;
      actions: string;
    };
    summary: (page: number, totalPages: number, totalItems: number, selected: number) => string;
  };
  zip: {
    summaryReady: (count: number, formats: string[], max: number) => string;
    summaryNeedFormat: string;
    summaryNeedSelection: string;
    cacheLabel: (filename: string) => string;
    formats: Record<ZipOptionKey, string>;
  };
  status: {
    cancelFetch: string;
    categoryStart: string;
    categoryBatch: (chunk: number, start: number, end: number) => string;
    categoryCancelled: string;
    userStart: string;
    userBatch: (chunk: number, start: number, end: number) => string;
    userCancelled: string;
    decoderInit: string;
    downloadBinary: string;
    zipInit: string;
    zipProgress: (current: number, total: number, label: string) => string;
    zipFinalizing: string;
    zipReady: string;
    zipFailed: string;
  };
  previewTitle: string;
  errors: {
    contexts: {
      login: string;
      search: string;
      category: string;
      user: string;
      decode: string;
      raw: string;
      zip: string;
    };
    api: (context: string, code: number) => string;
    generic: (message: string) => string;
  };
}

const translations: Record<Locale, Translation> = {
  en: {
    header: {
      title: 'servoom web',
      tagline: 'Divoom Cloud data export tool',
      footer: '❤️ pixel art, ❤️ pixel artists.',
      languageLabel: 'Language',
    },
    panels: {
      signIn: '1. Sign in',
      chooseSource: '2. Choose source',
      results: '3. Results',
      download: '4. Download selection',
    },
    mode: { category: 'By category', user: 'By user' },
    buttons: {
      signIn: 'Sign in to Divoom Cloud',
      logout: 'Log out',
      fetch: 'Fetch artworks',
      search: 'Search',
      clear: 'Clear',
      select: 'Select',
      decode: 'Decode',
      decoding: 'Decoding…',
      raw: 'Raw',
      buildZip: 'Build ZIP',
      downloadZip: 'Download ZIP',
      downloadWebp: 'Download WebP',
      downloadGif: 'Download GIF',
      downloadDat: 'Download DAT',
      cancelFetch: 'Cancel current fetch',
      selectPage: 'Select all (page)',
      unselectPage: 'Unselect all (page)',
      previousPage: 'Previous',
      nextPage: 'Next',
      loading: 'Loading…',
      searching: 'Searching…',
    },
    labels: {
      email: 'Email',
      password: 'Password or MD5 hash',
      passwordHashed: 'Password is already hashed',
      category: 'Category',
      start: 'Start #',
      count: 'Number of items',
      searchUsers: 'Search users',
      selectedUser: 'Selected user',
      resultsHeading: 'Results:',
      artist: 'Artist',
    },
    placeholders: { searchUsers: 'nickname fragment' },
    tooltips: {
      hash: 'Only select "Already hashed" if you know what an MD5 hash is. Otherwise, just enter your password.',
      fetchLogin: 'You need to log in first to fetch artworks',
      searchLogin: 'You need to log in first to search',
    },
    messages: {
      noDataset: 'No dataset loaded yet.',
      noItems: 'No items loaded yet.',
      previewPlaceholder: 'No artwork decoded yet. Click “Decode” on any row to preview it here.',
      unknownArtist: 'Unknown artist',
      loggedInAs: (email) => `Logged in as ${email}`,
      categoryLabel: (categoryId, start, end, count) =>
        `Category ${categoryId} · #${start}–#${end} (${count} items)`,
      userLabel: (nickname, userId, start, end, count) =>
        `User ${nickname} (#${userId}) · #${start}–#${end} (${count} items)`,
      userListEntry: (nickname, userId) => `${nickname} (#${userId})`,
      previewMeta: (width, height, frames, speed) =>
        `${width} × ${height} · ${frames} frames @${speed} ms`,
    },
    table: {
      headers: {
        select: 'Select',
        name: 'Name',
        id: 'ID',
        likes: 'Likes',
        views: 'Views',
        uploaded: 'Uploaded',
        size: 'Size',
        actions: 'Actions',
      },
      summary: (page, totalPages, totalItems, selected) =>
        `Page ${page} / ${totalPages} · ${totalItems} items · ${selected} selected`,
    },
    zip: {
      summaryReady: (count, formats, max) =>
        `Ready to bundle ${count} artwork${count === 1 ? '' : 's'} as ${formats.join(', ')} (max ${max}).`,
      summaryNeedFormat: 'Enable at least one format above to export.',
      summaryNeedSelection: 'Select artworks above to enable ZIP export.',
      cacheLabel: (filename) => `Last ZIP: ${filename}`,
      formats: { webp: 'WebP', gif: 'GIF', dat: 'DAT (raw)' },
    },
    status: {
      cancelFetch: 'Cancelling current fetch…',
      categoryStart: 'Starting category fetch…',
      categoryBatch: (chunk, start, end) => `Fetching category batch ${chunk}: #${start}–#${end}`,
      categoryCancelled: 'Category fetch cancelled',
      userStart: 'Starting user fetch…',
      userBatch: (chunk, start, end) => `Fetching user batch ${chunk}: #${start}–#${end}`,
      userCancelled: 'User fetch cancelled',
      decoderInit: 'Initializing decoder…',
      downloadBinary: 'Downloading binary payload…',
      zipInit: 'Initializing ZIP export…',
      zipProgress: (current, total, label) => `Zipping ${current}/${total}: ${label}`,
      zipFinalizing: 'Finalizing ZIP archive…',
      zipReady: 'ZIP download ready',
      zipFailed: 'ZIP creation failed',
    },
    previewTitle: 'Preview & export single artwork',
    errors: {
      contexts: {
        login: 'Sign in',
        search: 'User search',
        category: 'Category fetch',
        user: 'User gallery fetch',
        decode: 'Decode',
        raw: 'Raw download',
        zip: 'ZIP export',
      },
      api: (context, code) => `${context} failed (code ${code}).`,
      generic: (message) => message,
    },
  },
  es: {
    header: {
      title: 'servoom web',
      tagline: 'Herramienta de exportación de datos de Divoom Cloud',
      footer: '❤️ pixel art, ❤️ artistas de píxel.',
      languageLabel: 'Idioma',
    },
    panels: {
      signIn: '1. Inicia sesión',
      chooseSource: '2. Elige la fuente',
      results: '3. Resultados',
      download: '4. Descargar selección',
    },
    mode: { category: 'Por categoría', user: 'Por usuario' },
    buttons: {
      signIn: 'Iniciar sesión en Divoom Cloud',
      logout: 'Cerrar sesión',
      fetch: 'Obtener obras',
      search: 'Buscar',
      clear: 'Limpiar',
      select: 'Seleccionar',
      decode: 'Decodificar',
      decoding: 'Decodificando…',
      raw: 'Bruto',
      buildZip: 'Generar ZIP',
      downloadZip: 'Descargar ZIP',
      downloadWebp: 'Descargar WebP',
      downloadGif: 'Descargar GIF',
      downloadDat: 'Descargar DAT',
      cancelFetch: 'Cancelar la descarga',
      selectPage: 'Seleccionar todo (página)',
      unselectPage: 'Deseleccionar todo (página)',
      previousPage: 'Anterior',
      nextPage: 'Siguiente',
      loading: 'Cargando…',
      searching: 'Buscando…',
    },
    labels: {
      email: 'Correo electrónico',
      password: 'Contraseña o hash MD5',
      passwordHashed: 'La contraseña ya está hasheada',
      category: 'Categoría',
      start: 'Inicio #',
      count: 'Cantidad de elementos',
      searchUsers: 'Buscar usuarios',
      selectedUser: 'Usuario seleccionado',
      resultsHeading: 'Resultados:',
      artist: 'Artista',
    },
    placeholders: { searchUsers: 'fragmento del apodo' },
    tooltips: {
      hash: 'Activa “Ya está hasheada” solo si sabes qué es un hash MD5. Si no, escribe tu contraseña.',
      fetchLogin: 'Debes iniciar sesión para obtener obras.',
      searchLogin: 'Debes iniciar sesión para buscar.',
    },
    messages: {
      noDataset: 'Todavía no se ha cargado ningún conjunto.',
      noItems: 'Aún no hay elementos cargados.',
      previewPlaceholder:
        'Aún no se ha decodificado ninguna obra. Pulsa “Decodificar” en cualquier fila para verla aquí.',
      unknownArtist: 'Artista desconocido',
      loggedInAs: (email) => `Sesión iniciada como ${email}`,
      categoryLabel: (categoryId, start, end, count) =>
        `Categoría ${categoryId} · #${start}-#${end} (${count} obras)`,
      userLabel: (nickname, userId, start, end, count) =>
        `Usuario ${nickname} (#${userId}) · #${start}-#${end} (${count} obras)`,
      userListEntry: (nickname, userId) => `${nickname} (#${userId})`,
      previewMeta: (width, height, frames, speed) =>
        `${width} × ${height} · ${frames} fotogramas @${speed} ms`,
    },
    table: {
      headers: {
        select: 'Seleccionar',
        name: 'Nombre',
        id: 'ID',
        likes: 'Me gusta',
        views: 'Vistas',
        uploaded: 'Subido',
        size: 'Tamaño',
        actions: 'Acciones',
      },
      summary: (page, totalPages, totalItems, selected) =>
        `Página ${page} / ${totalPages} · ${totalItems} elementos · ${selected} seleccionados`,
    },
    zip: {
      summaryReady: (count, formats, max) =>
        `Listo para agrupar ${count} obra${count === 1 ? '' : 's'} como ${formats.join(', ')} (máximo ${max}).`,
      summaryNeedFormat: 'Activa al menos un formato para exportar.',
      summaryNeedSelection: 'Selecciona obras para habilitar el ZIP.',
      cacheLabel: (filename) => `Último ZIP: ${filename}`,
      formats: { webp: 'WebP', gif: 'GIF', dat: 'DAT (bruto)' },
    },
    status: {
      cancelFetch: 'Cancelando la descarga…',
      categoryStart: 'Iniciando la descarga de la categoría…',
      categoryBatch: (chunk, start, end) =>
        `Descargando lote ${chunk} de la categoría: #${start}-#${end}`,
      categoryCancelled: 'Descarga de categoría cancelada',
      userStart: 'Iniciando la descarga del usuario…',
      userBatch: (chunk, start, end) =>
        `Descargando lote ${chunk} del usuario: #${start}-#${end}`,
      userCancelled: 'Descarga de usuario cancelada',
      decoderInit: 'Inicializando el decodificador…',
      downloadBinary: 'Descargando datos binarios…',
      zipInit: 'Iniciando la exportación ZIP…',
      zipProgress: (current, total, label) => `Empaquetando ${current}/${total}: ${label}`,
      zipFinalizing: 'Finalizando el ZIP…',
      zipReady: 'ZIP listo para descargar',
      zipFailed: 'Error al crear el ZIP',
    },
    previewTitle: 'Vista previa y exportación de una sola obra',
    errors: {
      contexts: {
        login: 'Inicio de sesión',
        search: 'Búsqueda de usuarios',
        category: 'Descarga de categoría',
        user: 'Descarga de usuario',
        decode: 'Decodificación',
        raw: 'Descarga bruta',
        zip: 'Exportación ZIP',
      },
      api: (context, code) => `${context} falló (código ${code}).`,
      generic: (message) => `Error: ${message}`,
    },
  },
  zh: {
    header: {
      title: 'servoom web',
      tagline: 'Divoom Cloud 数据导出工具',
      footer: '❤️ 像素艺术，❤️ 像素艺术家。',
      languageLabel: '语言',
    },
    panels: {
      signIn: '1. 登录',
      chooseSource: '2. 选择来源',
      results: '3. 结果',
      download: '4. 下载所选项目',
    },
    mode: { category: '按分类', user: '按用户' },
    buttons: {
      signIn: '登录 Divoom Cloud',
      logout: '退出登录',
      fetch: '获取作品',
      search: '搜索',
      clear: '清除',
      select: '选择',
      decode: '解码',
      decoding: '正在解码…',
      raw: '原始',
      buildZip: '生成 ZIP',
      downloadZip: '下载 ZIP',
      downloadWebp: '下载 WebP',
      downloadGif: '下载 GIF',
      downloadDat: '下载 DAT',
      cancelFetch: '取消当前获取',
      selectPage: '本页全选',
      unselectPage: '本页全不选',
      previousPage: '上一页',
      nextPage: '下一页',
      loading: '加载中…',
      searching: '搜索中…',
    },
    labels: {
      email: '邮箱',
      password: '密码或 MD5 哈希',
      passwordHashed: '密码已是哈希值',
      category: '分类',
      start: '起始 #',
      count: '项目数量',
      searchUsers: '搜索用户',
      selectedUser: '已选用户',
      resultsHeading: '结果：',
      artist: '创作者',
    },
    placeholders: { searchUsers: '昵称片段' },
    tooltips: {
      hash: '只有了解 MD5 哈希时才选择“密码已是哈希值”，否则请输入普通密码。',
      fetchLogin: '获取作品前请先登录。',
      searchLogin: '搜索前请先登录。',
    },
    messages: {
      noDataset: '尚未加载任何数据。',
      noItems: '尚未加载作品。',
      previewPlaceholder: '尚未解码任何作品。点击任意行的“解码”即可在此预览。',
      unknownArtist: '未知创作者',
      loggedInAs: (email) => `已登录：${email}`,
      categoryLabel: (categoryId, start, end, count) =>
        `分类 ${categoryId} · #${start}–#${end}（${count} 个）`,
      userLabel: (nickname, userId, start, end, count) =>
        `用户 ${nickname} (#${userId}) · #${start}–#${end}（${count} 个）`,
      userListEntry: (nickname, userId) => `${nickname} (#${userId})`,
      previewMeta: (width, height, frames, speed) =>
        `${width} × ${height} · ${frames} 帧 @${speed} ms`,
    },
    table: {
      headers: {
        select: '选择',
        name: '名称',
        id: 'ID',
        likes: '点赞',
        views: '浏览',
        uploaded: '上传时间',
        size: '尺寸',
        actions: '操作',
      },
      summary: (page, totalPages, totalItems, selected) =>
        `第 ${page}/${totalPages} 页 · 共 ${totalItems} 项 · 选中 ${selected} 项`,
    },
    zip: {
      summaryReady: (count, formats, max) =>
        `可将 ${count} 个作品导出为 ${formats.join('、')}（最多 ${max} 个）。`,
      summaryNeedFormat: '请至少选择一种导出格式。',
      summaryNeedSelection: '请选择上方的作品以启用 ZIP。',
      cacheLabel: (filename) => `最新 ZIP：${filename}`,
      formats: { webp: 'WebP', gif: 'GIF', dat: 'DAT（原始）' },
    },
    status: {
      cancelFetch: '正在取消当前获取…',
      categoryStart: '正在开始分类获取…',
      categoryBatch: (chunk, start, end) =>
        `正在获取分类批次 ${chunk}：#${start}–#${end}`,
      categoryCancelled: '分类获取已取消',
      userStart: '正在开始用户获取…',
      userBatch: (chunk, start, end) =>
        `正在获取用户批次 ${chunk}：#${start}–#${end}`,
      userCancelled: '用户获取已取消',
      decoderInit: '正在初始化解码器…',
      downloadBinary: '正在下载二进制数据…',
      zipInit: '正在初始化 ZIP 导出…',
      zipProgress: (current, total, label) => `压缩 ${current}/${total}：${label}`,
      zipFinalizing: '正在完成 ZIP…',
      zipReady: 'ZIP 可供下载',
      zipFailed: '创建 ZIP 失败',
    },
    previewTitle: '单个作品预览与导出',
    errors: {
      contexts: {
        login: '登录',
        search: '用户搜索',
        category: '分类获取',
        user: '用户获取',
        decode: '解码',
        raw: '原始下载',
        zip: 'ZIP 导出',
      },
      api: (context, code) => `${context} 失败（代码 ${code}）。`,
      generic: (message) => `错误：${message}`,
    },
  },
  ja: {
    header: {
      title: 'servoom web',
      tagline: 'Divoom Cloud データエクスポートツール',
      footer: '❤️ ピクセルアート、❤️ ピクセルアーティスト。',
      languageLabel: '言語',
    },
    panels: {
      signIn: '1. サインイン',
      chooseSource: '2. 取得元を選択',
      results: '3. 結果',
      download: '4. 選択した作品をダウンロード',
    },
    mode: { category: 'カテゴリ別', user: 'ユーザー別' },
    buttons: {
      signIn: 'Divoom Cloud にサインイン',
      logout: 'サインアウト',
      fetch: '作品を取得',
      search: '検索',
      clear: 'クリア',
      select: '選択',
      decode: 'デコード',
      decoding: 'デコード中…',
      raw: '生データ',
      buildZip: 'ZIP を作成',
      downloadZip: 'ZIP をダウンロード',
      downloadWebp: 'WebP をダウンロード',
      downloadGif: 'GIF をダウンロード',
      downloadDat: 'DAT をダウンロード',
      cancelFetch: '取得をキャンセル',
      selectPage: 'ページ全てを選択',
      unselectPage: 'ページ全てを解除',
      previousPage: '前へ',
      nextPage: '次へ',
      loading: '読み込み中…',
      searching: '検索中…',
    },
    labels: {
      email: 'メールアドレス',
      password: 'パスワードまたは MD5 ハッシュ',
      passwordHashed: 'パスワードはすでにハッシュ化してある',
      category: 'カテゴリ',
      start: '開始 #',
      count: '件数',
      searchUsers: 'ユーザー検索',
      selectedUser: '選択したユーザー',
      resultsHeading: '結果：',
      artist: 'アーティスト',
    },
    placeholders: { searchUsers: 'ニックネームの一部' },
    tooltips: {
      hash: 'MD5 ハッシュを理解している場合のみ「パスワードはすでにハッシュ化してある」を選択してください。',
      fetchLogin: '作品を取得するにはログインが必要です。',
      searchLogin: '検索するにはログインが必要です。',
    },
    messages: {
      noDataset: 'まだデータセットが読み込まれていません。',
      noItems: 'まだ作品が読み込まれていません。',
      previewPlaceholder: 'まだ作品をデコードしていません。「デコード」を押すとここに表示されます。',
      unknownArtist: '不明なアーティスト',
      loggedInAs: (email) => `${email} としてサインイン済み`,
      categoryLabel: (categoryId, start, end, count) =>
        `カテゴリ ${categoryId} · #${start}〜#${end}（${count} 件）`,
      userLabel: (nickname, userId, start, end, count) =>
        `ユーザー ${nickname} (#${userId}) · #${start}〜#${end}（${count} 件）`,
      userListEntry: (nickname, userId) => `${nickname} (#${userId})`,
      previewMeta: (width, height, frames, speed) =>
        `${width} × ${height} · ${frames} フレーム @${speed} ms`,
    },
    table: {
      headers: {
        select: '選択',
        name: '名前',
        id: 'ID',
        likes: 'いいね',
        views: '閲覧',
        uploaded: 'アップロード',
        size: 'サイズ',
        actions: '操作',
      },
      summary: (page, totalPages, totalItems, selected) =>
        `ページ ${page} / ${totalPages} · ${totalItems} 件 · ${selected} 件を選択`,
    },
    zip: {
      summaryReady: (count, formats, max) =>
        `${count} 件の作品を ${formats.join('、')} としてまとめます（最大 ${max}）。`,
      summaryNeedFormat: 'エクスポート形式を少なくとも 1 つ選択してください。',
      summaryNeedSelection: '上の作品を選択すると ZIP が有効になります。',
      cacheLabel: (filename) => `最新の ZIP: ${filename}`,
      formats: { webp: 'WebP', gif: 'GIF', dat: 'DAT (生データ)' },
    },
    status: {
      cancelFetch: '取得をキャンセルしています…',
      categoryStart: 'カテゴリ取得を開始しています…',
      categoryBatch: (chunk, start, end) => `カテゴリのバッチ ${chunk} を取得中: #${start}〜#${end}`,
      categoryCancelled: 'カテゴリ取得をキャンセルしました',
      userStart: 'ユーザー取得を開始しています…',
      userBatch: (chunk, start, end) => `ユーザーのバッチ ${chunk} を取得中: #${start}〜#${end}`,
      userCancelled: 'ユーザー取得をキャンセルしました',
      decoderInit: 'デコーダーを初期化しています…',
      downloadBinary: 'バイナリをダウンロードしています…',
      zipInit: 'ZIP エクスポートを初期化しています…',
      zipProgress: (current, total, label) => `${current}/${total} を圧縮中: ${label}`,
      zipFinalizing: 'ZIP を最終処理しています…',
      zipReady: 'ZIP のダウンロード準備完了',
      zipFailed: 'ZIP の作成に失敗しました',
    },
    previewTitle: '単一作品のプレビューとエクスポート',
    errors: {
      contexts: {
        login: 'サインイン',
        search: 'ユーザー検索',
        category: 'カテゴリ取得',
        user: 'ユーザー取得',
        decode: 'デコード',
        raw: '生データのダウンロード',
        zip: 'ZIP エクスポート',
      },
      api: (context, code) => `${context} に失敗しました（コード ${code}）。`,
      generic: (message) => `エラー: ${message}`,
    },
  },
  ru: {
    header: {
      title: 'servoom web',
      tagline: 'Инструмент экспорта данных Divoom Cloud',
      footer: '❤️ пиксель-арт, ❤️ художники пикселей.',
      languageLabel: 'Язык',
    },
    panels: {
      signIn: '1. Войдите',
      chooseSource: '2. Выберите источник',
      results: '3. Результаты',
      download: '4. Скачать выбранное',
    },
    mode: { category: 'По категории', user: 'По пользователю' },
    buttons: {
      signIn: 'Войти в Divoom Cloud',
      logout: 'Выйти',
      fetch: 'Получить работы',
      search: 'Поиск',
      clear: 'Очистить',
      select: 'Выбрать',
      decode: 'Декодировать',
      decoding: 'Декодирование…',
      raw: 'RAW',
      buildZip: 'Собрать ZIP',
      downloadZip: 'Скачать ZIP',
      downloadWebp: 'Скачать WebP',
      downloadGif: 'Скачать GIF',
      downloadDat: 'Скачать DAT',
      cancelFetch: 'Отменить загрузку',
      selectPage: 'Выбрать всё (страница)',
      unselectPage: 'Снять выбор (страница)',
      previousPage: 'Назад',
      nextPage: 'Вперёд',
      loading: 'Загрузка…',
      searching: 'Поиск…',
    },
    labels: {
      email: 'Email',
      password: 'Пароль или MD5-хеш',
      passwordHashed: 'Пароль уже захеширован',
      category: 'Категория',
      start: 'Старт #',
      count: 'Количество элементов',
      searchUsers: 'Поиск пользователей',
      selectedUser: 'Выбранный пользователь',
      resultsHeading: 'Результаты:',
      artist: 'Автор',
    },
    placeholders: { searchUsers: 'часть ника' },
    tooltips: {
      hash: 'Выбирайте «Пароль уже захеширован» только если понимаете, что такое MD5-хеш. Иначе введите обычный пароль.',
      fetchLogin: 'Сначала войдите, чтобы получать работы.',
      searchLogin: 'Сначала войдите, чтобы искать.',
    },
    messages: {
      noDataset: 'Данные ещё не загружены.',
      noItems: 'Пока нет загруженных работ.',
      previewPlaceholder: 'Работы ещё не декодированы. Нажмите «Декодировать» в таблице, чтобы увидеть их здесь.',
      unknownArtist: 'Неизвестный автор',
      loggedInAs: (email) => `Вы вошли как ${email}`,
      categoryLabel: (categoryId, start, end, count) =>
        `Категория ${categoryId} · #${start}–#${end} (${count} шт.)`,
      userLabel: (nickname, userId, start, end, count) =>
        `Пользователь ${nickname} (#${userId}) · #${start}–#${end} (${count} шт.)`,
      userListEntry: (nickname, userId) => `${nickname} (#${userId})`,
      previewMeta: (width, height, frames, speed) =>
        `${width} × ${height} · ${frames} кадров @${speed} мс`,
    },
    table: {
      headers: {
        select: 'Выбор',
        name: 'Имя',
        id: 'ID',
        likes: 'Лайки',
        views: 'Просмотры',
        uploaded: 'Загрузка',
        size: 'Размер',
        actions: 'Действия',
      },
      summary: (page, totalPages, totalItems, selected) =>
        `Стр. ${page}/${totalPages} · ${totalItems} элементов · выбрано ${selected}`,
    },
    zip: {
      summaryReady: (count, formats, max) =>
        `Можно упаковать ${count} работ в ${formats.join(', ')} (макс. ${max}).`,
      summaryNeedFormat: 'Выберите хотя бы один формат выше.',
      summaryNeedSelection: 'Выберите работы выше, чтобы включить ZIP.',
      cacheLabel: (filename) => `Последний ZIP: ${filename}`,
      formats: { webp: 'WebP', gif: 'GIF', dat: 'DAT (сырой)' },
    },
    status: {
      cancelFetch: 'Отмена текущей загрузки…',
      categoryStart: 'Запуск загрузки категории…',
      categoryBatch: (chunk, start, end) =>
        `Категория, пакет ${chunk}: #${start}–#${end}`,
      categoryCancelled: 'Загрузка категории отменена',
      userStart: 'Запуск загрузки пользователя…',
      userBatch: (chunk, start, end) =>
        `Пользователь, пакет ${chunk}: #${start}–#${end}`,
      userCancelled: 'Загрузка пользователя отменена',
      decoderInit: 'Инициализация декодера…',
      downloadBinary: 'Загрузка бинарных данных…',
      zipInit: 'Инициализация экспорта ZIP…',
      zipProgress: (current, total, label) => `Архивируем ${current}/${total}: ${label}`,
      zipFinalizing: 'Завершение ZIP…',
      zipReady: 'ZIP готов к загрузке',
      zipFailed: 'Сбой при создании ZIP',
    },
    previewTitle: 'Предпросмотр и экспорт одной работы',
    errors: {
      contexts: {
        login: 'Вход',
        search: 'Поиск пользователей',
        category: 'Загрузка категории',
        user: 'Загрузка пользователя',
        decode: 'Декодирование',
        raw: 'RAW-загрузка',
        zip: 'Экспорт ZIP',
      },
      api: (context, code) => `${context} не выполнен (код ${code}).`,
      generic: (message) => `Ошибка: ${message}`,
    },
  },
};

const localeOptions: Array<{ locale: Locale; flag: string; label: string }> = [
  { locale: 'en', flag: '🇺🇸', label: 'English' },
  { locale: 'es', flag: '🇪🇸', label: 'Español' },
  { locale: 'zh', flag: '🇨🇳', label: '中文' },
  { locale: 'ja', flag: '🇯🇵', label: '日本語' },
  { locale: 'ru', flag: '🇷🇺', label: 'Русский' },
];

class CancelledError extends Error {
  constructor() {
    super('Operation cancelled');
    this.name = 'CancelledError';
  }
}

type FetchContext =
  | { type: 'category'; categoryId: number; start: number; count: number }
  | { type: 'user'; userId: number; nickName: string; start: number; count: number };

type StatusDescriptor =
  | { type: 'cancelFetch' }
  | { type: 'categoryStart' }
  | { type: 'categoryBatch'; chunk: number; start: number; end: number }
  | { type: 'categoryCancelled' }
  | { type: 'userStart' }
  | { type: 'userBatch'; chunk: number; start: number; end: number }
  | { type: 'userCancelled' }
  | { type: 'decoderInit' }
  | { type: 'downloadBinary' };

type ZipStatusDescriptor =
  | { type: 'init' }
  | { type: 'progress'; current: number; total: number; label: string }
  | { type: 'finalizing' }
  | { type: 'ready' }
  | { type: 'failed' };

type ErrorContext = 'login' | 'search' | 'category' | 'user' | 'decode' | 'raw' | 'zip';

type UiError =
  | { type: 'api'; context: ErrorContext; code: number }
  | { type: 'generic'; message: string };

type ItemsLabel =
  | { type: 'none' }
  | { type: 'category'; categoryId: number; start: number; end: number; count: number }
  | { type: 'user'; nickname: string; userId: number; start: number; end: number; count: number };

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

function isLocale(value: string): value is Locale {
  return value in translations;
}

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

function resolveArtistName(item: GalleryInfo, t: Translation): string {
  const username = item.UserName?.trim();
  if (username) return username;
  const nickname = (item as { NickName?: string }).NickName?.trim();
  if (nickname) return nickname;
  if (item.UserId) return `#${item.UserId}`;
  return t.messages.unknownArtist;
}

function formatItemsLabel(label: ItemsLabel, t: Translation): string {
  if (label.type === 'category') {
    return t.messages.categoryLabel(label.categoryId, label.start, label.end, label.count);
  }
  if (label.type === 'user') {
    return t.messages.userLabel(label.nickname, label.userId, label.start, label.end, label.count);
  }
  return t.messages.noDataset;
}

function formatStatusMessage(status: StatusDescriptor, t: Translation): string {
  switch (status.type) {
    case 'cancelFetch':
      return t.status.cancelFetch;
    case 'categoryStart':
      return t.status.categoryStart;
    case 'categoryBatch':
      return t.status.categoryBatch(status.chunk, status.start, status.end);
    case 'categoryCancelled':
      return t.status.categoryCancelled;
    case 'userStart':
      return t.status.userStart;
    case 'userBatch':
      return t.status.userBatch(status.chunk, status.start, status.end);
    case 'userCancelled':
      return t.status.userCancelled;
    case 'decoderInit':
      return t.status.decoderInit;
    case 'downloadBinary':
      return t.status.downloadBinary;
    default:
      return '';
  }
}

function formatZipStatusMessage(zipStatus: ZipStatusDescriptor, t: Translation): string {
  switch (zipStatus.type) {
    case 'init':
      return t.status.zipInit;
    case 'progress':
      return t.status.zipProgress(zipStatus.current, zipStatus.total, zipStatus.label);
    case 'finalizing':
      return t.status.zipFinalizing;
    case 'ready':
      return t.status.zipReady;
    case 'failed':
      return t.status.zipFailed;
    default:
      return '';
  }
}

function formatErrorMessage(error: UiError, t: Translation): string {
  if (error.type === 'api') {
    const context = t.errors.contexts[error.context];
    return t.errors.api(context, error.code);
  }
  return t.errors.generic(error.message);
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

function App() {
  const decoder = useMemo(() => new PyodideDecoder(), []);
  const downloadCache = useRef<Map<number, Uint8Array>>(new Map());
  const decodedCache = useRef<Map<number, DecodedBean>>(new Map());

  const [locale, setLocale] = useState<Locale>('en');
  const t = translations[locale];

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const stored = window.localStorage.getItem(LOCALE_STORAGE_KEY);
    if (stored && isLocale(stored)) {
      setLocale(stored);
    }
  }, []);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    window.localStorage.setItem(LOCALE_STORAGE_KEY, locale);
  }, [locale]);

  const [session, setSession] = useState<Session | null>(null);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [passwordIsMd5, setPasswordIsMd5] = useState(false);
  const [loginError, setLoginError] = useState<UiError | null>(null);

  const [categoryId, setCategoryId] = useState(DEFAULT_CATEGORY);
  const [mode, setMode] = useState<'category' | 'user'>('category');
  const [range, setRange] = useState<{ start: number; count: number }>({ start: 1, count: 30 });

  const [items, setItems] = useState<GalleryInfo[]>([]);
  const [itemsLabel, setItemsLabel] = useState<ItemsLabel>({ type: 'none' });
  const [currentPage, setCurrentPage] = useState(0);
  const [selectionMap, setSelectionMap] = useState<Map<number, boolean>>(new Map());
  const [fetchContext, setFetchContext] = useState<FetchContext | null>(null);

  const [userQuery, setUserQuery] = useState('');
  const [userResults, setUserResults] = useState<UserSummary[]>([]);
  const [selectedUser, setSelectedUser] = useState<UserSummary | null>(null);
  const [searchingUsers, setSearchingUsers] = useState(false);

  const [itemsLoading, setItemsLoading] = useState(false);
  const [decodeState, setDecodeState] = useState<DecodeState | null>(null);
  const [status, setStatus] = useState<StatusDescriptor | null>(null);
  const [error, setError] = useState<UiError | null>(null);
  const [isZipping, setIsZipping] = useState(false);
  const [zipOptions, setZipOptions] = useState<Record<ZipOptionKey, boolean>>({
    webp: true,
    gif: true,
    dat: true,
  });
  const [zipStatus, setZipStatus] = useState<ZipStatusDescriptor | null>(null);
  const [zipCacheMeta, setZipCacheMeta] = useState<{ filename: string } | null>(null);
  const [decodingItemId, setDecodingItemId] = useState<number | null>(null);
  const zipCacheRef = useRef<{ url: string; filename: string } | null>(null);
  const cancelRef = useRef(false);

  useEffect(() => {
    return () => {
      if (zipCacheRef.current) {
        URL.revokeObjectURL(zipCacheRef.current.url);
        zipCacheRef.current = null;
      }
    };
  }, []);

  const paginatedItems = useMemo(() => {
    const start = currentPage * PAGE_SIZE;
    return items.slice(start, start + PAGE_SIZE);
  }, [items, currentPage]);

  const totalPages = Math.max(1, Math.ceil(items.length / PAGE_SIZE));
  const normalizedRange = useMemo(() => {
    const startValue = Number.isFinite(range.start) ? Math.max(1, Math.floor(range.start)) : 1;
    const countValue =
      Number.isFinite(range.count) && range.count > 0 ?
        Math.min(MAX_ITEMS, Math.floor(range.count)) :
        1;
    return { start: startValue, count: countValue, end: startValue + countValue - 1 };
  }, [range]);

  const selectedItems = useMemo(
    () => items.filter((item) => selectionMap.get(item.GalleryId)),
    [items, selectionMap],
  );
  const selectionCount = selectedItems.length;
  const pageHasItems = paginatedItems.length > 0;
  const currentPageSelected = paginatedItems.filter((item) => selectionMap.get(item.GalleryId)).length;
  const zipTypesSelected = zipOptions.webp || zipOptions.gif || zipOptions.dat;
  const selectedZipFormats = (Object.entries(zipOptions) as Array<[ZipOptionKey, boolean]>)
    .filter(([, enabled]) => enabled)
    .map(([key]) => t.zip.formats[key]);
  const decodingLocked = decodingItemId !== null;

  const statusText = status ? formatStatusMessage(status, t) : null;
  const errorText = error ? formatErrorMessage(error, t) : null;
  const loginErrorText = loginError ? formatErrorMessage(loginError, t) : null;
  const zipStatusText = zipStatus ? formatZipStatusMessage(zipStatus, t) : null;
  const itemsLabelText = formatItemsLabel(itemsLabel, t);

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
    setStatus({ type: 'cancelFetch' });
    setItemsLoading(false);
  };

  const handleZipOptionToggle = (key: ZipOptionKey) => {
    setZipOptions((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const renderPaginationControls = (className: string) => (
    <div className={className}>
      <div>
        <strong>{itemsLabelText}</strong>
        <div>
          {t.table.summary(currentPage + 1, totalPages, items.length, selectionCount)}
        </div>
      </div>
      <div className="results-tools">
        <button onClick={handleSelectCurrentPage} disabled={!pageHasItems}>
          {t.buttons.selectPage}
        </button>
        <button onClick={handleUnselectCurrentPage} disabled={!currentPageSelected}>
          {t.buttons.unselectPage}
        </button>
        <div className="actions">
          <button onClick={() => setCurrentPage((p) => Math.max(0, p - 1))} disabled={currentPage === 0}>
            {t.buttons.previousPage}
          </button>
          <button
            onClick={() => setCurrentPage((p) => Math.min(totalPages - 1, p + 1))}
            disabled={currentPage >= totalPages - 1}
          >
            {t.buttons.nextPage}
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
      setLoginError(null);
      logger.info('Login success', { userId: result.userId });
    } catch (err) {
      logger.error('Login failed', err);
      if (err instanceof ApiError) {
        setLoginError({ type: 'api', context: 'login', code: err.code });
      } else {
        setLoginError({ type: 'generic', message: (err as Error).message });
      }
    }
  };

  const handleLogout = () => {
    downloadCache.current.clear();
    decodedCache.current.clear();
    setSession(null);
    setLoginError(null);
    setItems([]);
    setItemsLabel({ type: 'none' });
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

  const resetDataset = (list: GalleryInfo[], context: FetchContext | null) => {
    const trimmed = list.slice(0, MAX_ITEMS);
    setItems(trimmed);
    if (context?.type === 'category') {
      setItemsLabel({
        type: 'category',
        categoryId: context.categoryId,
        start: context.start,
        end: context.start + context.count - 1,
        count: trimmed.length,
      });
    } else if (context?.type === 'user') {
      setItemsLabel({
        type: 'user',
        nickname: context.nickName,
        userId: context.userId,
        start: context.start,
        end: context.start + context.count - 1,
        count: trimmed.length,
      });
    } else {
      setItemsLabel({ type: 'none' });
    }
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
      if (collected.length === before) break;
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
    const { start, count } = normalizedRange;
    cancelRef.current = false;
    setStatus({ type: 'categoryStart' });
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
            setStatus({ type: 'categoryBatch', chunk, start: chunkStart, end: chunkEnd });
          },
          isCancelled: () => cancelRef.current,
        },
      );
      resetDataset(files, { type: 'category', categoryId, start, count });
      setStatus(null);
    } catch (err) {
      if (err instanceof CancelledError) {
        setError(null);
        setStatus({ type: 'categoryCancelled' });
        logger.info('Category fetch cancelled');
        clearStatus = false;
      } else {
        logger.error('Category fetch failed', err);
        if (err instanceof ApiError) {
          setError({ type: 'api', context: 'category', code: err.code });
        } else {
          setError({ type: 'generic', message: (err as Error).message });
        }
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
      logger.error('User search failed', err);
      if (err instanceof ApiError) {
        setError({ type: 'api', context: 'search', code: err.code });
      } else {
        setError({ type: 'generic', message: (err as Error).message });
      }
    } finally {
      setSearchingUsers(false);
    }
  };

  const handleFetchUserGallery = async () => {
    if (!session || !selectedUser) return;
    setItemsLoading(true);
    setError(null);
    const { start, count } = normalizedRange;
    cancelRef.current = false;
    setStatus({ type: 'userStart' });
    let clearStatus = true;
    try {
      logger.info('Fetching user gallery', { userId: selectedUser.UserId, start, count });
      const files = await fetchInBatches(
        start,
        count,
        (chunkStart, chunkEnd) => fetchUserGallery(session, selectedUser.UserId, chunkStart, chunkEnd),
        {
          onProgress: ({ chunk, start: chunkStart, end: chunkEnd }) => {
            setStatus({ type: 'userBatch', chunk, start: chunkStart, end: chunkEnd });
          },
          isCancelled: () => cancelRef.current,
        },
      );
      resetDataset(files, {
        type: 'user',
        userId: selectedUser.UserId,
        nickName: selectedUser.NickName,
        start,
        count,
      });
      setStatus(null);
    } catch (err) {
      if (err instanceof CancelledError) {
        setError(null);
        setStatus({ type: 'userCancelled' });
        logger.info('User fetch cancelled');
        clearStatus = false;
      } else {
        logger.error('User gallery fetch failed', err);
        if (err instanceof ApiError) {
          setError({ type: 'api', context: 'user', code: err.code });
        } else {
          setError({ type: 'generic', message: (err as Error).message });
        }
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
    setStatus({ type: 'downloadBinary' });
    logger.info('Downloading binary', { galleryId: item.GalleryId, fileId: item.FileId });
    try {
      const data = await downloadBinary(item.FileId);
      downloadCache.current.set(item.GalleryId, data);
      logger.info('Binary downloaded', { galleryId: item.GalleryId, bytes: data.length });
      return data;
    } finally {
      setStatus(null);
    }
  };

  const handleDecode = async (item: GalleryInfo) => {
    if (decodingLocked) return;
    setDecodingItemId(item.GalleryId);
    setError(null);
    try {
      logger.info('Decode requested', { galleryId: item.GalleryId });
      const raw = await fetchRaw(item);
      setStatus({ type: 'decoderInit' });
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
      logger.error('Decode failed', err);
      if (err instanceof ApiError) {
        setError({ type: 'api', context: 'decode', code: err.code });
      } else {
        setError({ type: 'generic', message: (err as Error).message });
      }
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
      logger.error('Raw download failed', err);
      if (err instanceof ApiError) {
        setError({ type: 'api', context: 'raw', code: err.code });
      } else {
        setError({ type: 'generic', message: (err as Error).message });
      }
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
    if (!selectionCount || !zipTypesSelected) return;
    if (zipCacheRef.current) {
      URL.revokeObjectURL(zipCacheRef.current.url);
      zipCacheRef.current = null;
      setZipCacheMeta(null);
    }
    setIsZipping(true);
    setError(null);
    setZipStatus({ type: 'init' });
    try {
      logger.info('Preparing ZIP', { selectionCount });
      const zip = new JSZip();
      const folderSegments =
        fetchContext?.type === 'category' ?
          ['servoom', `category-${fetchContext.categoryId}`] :
          fetchContext?.type === 'user' ?
            ['servoom', `user-${fetchContext.nickName}-${fetchContext.userId}`] :
            ['servoom', 'selection'];
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
        setZipStatus({ type: 'progress', current: i + 1, total: selectionCount, label: progressLabel });
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
      setZipStatus({ type: 'finalizing' });
      const blob = await zip.generateAsync({ type: 'blob' });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      const archiveLabel =
        fetchContext?.type === 'category' ?
          `category-${fetchContext.categoryId}` :
          fetchContext?.type === 'user' ?
            `user-${sanitizeSegment(fetchContext.nickName)}-${fetchContext.userId}` :
            'selection';
      const filename = `${archiveLabel}-${Date.now()}.zip`;
      anchor.download = filename;
      anchor.click();
      zipCacheRef.current = { url, filename };
      setZipCacheMeta({ filename });
      logger.info('ZIP download ready');
      setZipStatus({ type: 'ready' });
    } catch (err) {
      logger.error('ZIP creation failed', err);
      if (err instanceof ApiError) {
        setError({ type: 'api', context: 'zip', code: err.code });
      } else {
        setError({ type: 'generic', message: (err as Error).message });
      }
      setZipStatus({ type: 'failed' });
    } finally {
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
        <div className="header-row">
          <div>
            <h1>{t.header.title}</h1>
            <p>{t.header.tagline}</p>
          </div>
          <div className="language-switcher" aria-label={t.header.languageLabel}>
            {localeOptions.map((option) => (
              <button
                type="button"
                key={option.locale}
                className={option.locale === locale ? 'language-button active' : 'language-button'}
                onClick={() => setLocale(option.locale)}
                title={option.label}
              >
                {option.flag}
              </button>
            ))}
          </div>
        </div>
      </header>

      <section className="panel">
        <h2>{t.panels.signIn}</h2>
        {session ? (
          <div className="status success login-status">
            <span>{t.messages.loggedInAs(session.email)}</span>
            <button type="button" onClick={handleLogout}>
              {t.buttons.logout}
            </button>
          </div>
        ) : (
          <form className="grid-form" onSubmit={handleLogin}>
            <label>
              {t.labels.email}
              <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
            </label>
            <label title={t.tooltips.hash}>
              {t.labels.password}
              <input
                type="text"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                title={t.tooltips.hash}
              />
            </label>
            <label className="checkbox" title={t.tooltips.hash}>
              <input
                type="checkbox"
                checked={passwordIsMd5}
                onChange={(e) => setPasswordIsMd5(e.target.checked)}
                title={t.tooltips.hash}
              />
              {t.labels.passwordHashed}
            </label>
            <button type="submit">{t.buttons.signIn}</button>
            {loginErrorText && <div className="status error">{loginErrorText}</div>}
          </form>
        )}
      </section>

      <section className="panel">
        <h2>{t.panels.chooseSource}</h2>
        <div className="mode-toggle">
          <button
            type="button"
            className={mode === 'category' ? 'active' : ''}
            onClick={() => setMode('category')}
          >
            {t.mode.category}
          </button>
          <button
            type="button"
            className={mode === 'user' ? 'active' : ''}
            onClick={() => setMode('user')}
          >
            {t.mode.user}
          </button>
        </div>

        {mode === 'category' && (
          <div className="mode-panel">
            <div className="grid-form">
              <label>
                {t.labels.category}
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
                {t.labels.start}
                <input
                  type="number"
                  value={range.start}
                  min={1}
                  onChange={(e) => {
                    const raw = Number(e.target.value);
                    setRange((prev) => ({
                      ...prev,
                      start: Number.isFinite(raw) && raw > 0 ? Math.floor(raw) : 1,
                    }));
                  }}
                />
              </label>
              <label>
                {t.labels.count}
                <input
                  type="number"
                  value={Number.isFinite(range.count) ? range.count : ''}
                  min={1}
                  onBlur={(e) => {
                    const raw = Number(e.target.value);
                    setRange((prev) => ({
                      ...prev,
                      count:
                        Number.isFinite(raw) && raw > 0 ?
                          Math.min(MAX_ITEMS, Math.floor(raw)) :
                          1,
                    }));
                  }}
                  onChange={(e) => {
                    const { value } = e.target;
                    setRange((prev) => ({
                      ...prev,
                      count:
                        value === '' ?
                          NaN :
                          Number.isFinite(Number(value)) ? Number(value) : prev.count,
                    }));
                  }}
                />
              </label>
              <button
                onClick={handleFetchCategory}
                disabled={!session || itemsLoading}
                title={!session ? t.tooltips.fetchLogin : undefined}
              >
                {itemsLoading ? t.buttons.loading : t.buttons.fetch}
              </button>
            </div>
          </div>
        )}

        {mode === 'user' && (
          <div className="mode-panel">
            <div className="grid-form">
              <label>
                {t.labels.searchUsers}
                <input
                  type="text"
                  value={userQuery}
                  placeholder={t.placeholders.searchUsers}
                  onChange={(e) => setUserQuery(e.target.value)}
                />
              </label>
              <button
                onClick={handleSearchUsers}
                disabled={!session || searchingUsers}
                title={!session ? t.tooltips.searchLogin : undefined}
              >
                {searchingUsers ? t.buttons.searching : t.buttons.search}
              </button>
            </div>
            {userResults.length > 0 && (
              <div className="user-results">
                <strong>{t.labels.resultsHeading}</strong>
                <ul>
                  {userResults.map((user) => (
                    <li key={user.UserId}>
                      {t.messages.userListEntry(user.NickName, user.UserId)}{' '}
                      <button type="button" onClick={() => setSelectedUser(user)}>
                        {t.buttons.select}
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {selectedUser && (
              <>
                <div className="selected-user">
                  {t.labels.selectedUser}:{' '}
                  <strong>{t.messages.userListEntry(selectedUser.NickName, selectedUser.UserId)}</strong>
                  <button type="button" onClick={() => setSelectedUser(null)}>
                    {t.buttons.clear}
                  </button>
                </div>
                <div className="grid-form">
                  <label>
                    {t.labels.start}
                    <input
                      type="number"
                      value={range.start}
                      min={1}
                      onChange={(e) => {
                        const raw = Number(e.target.value);
                        setRange((prev) => ({
                          ...prev,
                          start: Number.isFinite(raw) && raw > 0 ? Math.floor(raw) : 1,
                        }));
                      }}
                    />
                  </label>
                  <label>
                    {t.labels.count}
                    <input
                      type="number"
                      value={Number.isFinite(range.count) ? range.count : ''}
                      min={1}
                      onBlur={(e) => {
                        const raw = Number(e.target.value);
                        setRange((prev) => ({
                          ...prev,
                          count:
                            Number.isFinite(raw) && raw > 0 ?
                              Math.min(MAX_ITEMS, Math.floor(raw)) :
                              1,
                        }));
                      }}
                      onChange={(e) => {
                        const { value } = e.target;
                        setRange((prev) => ({
                          ...prev,
                          count:
                            value === '' ?
                              NaN :
                              Number.isFinite(Number(value)) ? Number(value) : prev.count,
                        }));
                      }}
                    />
                  </label>
                  <button
                    onClick={handleFetchUserGallery}
                    disabled={!session || itemsLoading || !selectedUser}
                    title={!session ? t.tooltips.fetchLogin : undefined}
                  >
                    {itemsLoading ? t.buttons.loading : t.buttons.fetch}
                  </button>
                </div>
              </>
            )}
          </div>
        )}
      </section>

      {(statusText || errorText) && (
        <div className="status-stack">
          {statusText && <div className="status info">{statusText}</div>}
          {errorText && <div className="status error">{errorText}</div>}
        </div>
      )}
      {itemsLoading && (
        <div className="cancel-bar">
          <button type="button" onClick={handleCancelFetch}>
            {t.buttons.cancelFetch}
          </button>
        </div>
      )}

      <section className="panel">
        <h2>{t.panels.results}</h2>
        {renderPaginationControls('results-header')}

        {paginatedItems.length ? (
          <>
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>{t.table.headers.select}</th>
                    <th>{t.table.headers.name}</th>
                    <th>{t.table.headers.id}</th>
                    <th>{t.table.headers.likes}</th>
                    <th>{t.table.headers.views}</th>
                    <th>{t.table.headers.uploaded}</th>
                    <th>{t.table.headers.size}</th>
                    <th>{t.table.headers.actions}</th>
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
                          {decodingItemId === item.GalleryId ? t.buttons.decoding : t.buttons.decode}
                        </button>
                        <button onClick={() => handleDownloadRaw(item)}>{t.buttons.raw}</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {renderPaginationControls('results-footer')}
          </>
        ) : (
          <p>{t.messages.noItems}</p>
        )}
        <div className="preview-panel">
          <h3>{t.previewTitle}</h3>
          {decodeState ? (
            <>
              <div className="decode-meta">
                <div>
                  <strong>{decodeState.item.FileName}</strong>
                  <div>{`ID #${decodeState.item.GalleryId}`}</div>
                  <div>
                    {t.labels.artist}:{' '}
                    <span className="artist-name">{resolveArtistName(decodeState.item, t)}</span>
                  </div>
                  <div>
                    {t.messages.previewMeta(
                      decodeState.bean.columnCount * 16,
                      decodeState.bean.rowCount * 16,
                      decodeState.bean.totalFrames,
                      decodeState.bean.speed,
                    )}
                  </div>
                </div>
                <div className="preview-actions">
                  <button onClick={handleDownloadWebp}>{t.buttons.downloadWebp}</button>
                  <button onClick={handleDownloadGif}>{t.buttons.downloadGif}</button>
                  <button onClick={() => blobDownload(decodeState.raw, `${decodeState.item.GalleryId}.dat`)}>
                    {t.buttons.downloadDat}
                  </button>
                </div>
              </div>
              <AnimationPreview bean={decodeState.bean} scale={scale} />
            </>
          ) : (
            <p>{t.messages.previewPlaceholder}</p>
          )}
        </div>
      </section>

      <section className="panel">
        <h2>{t.panels.download}</h2>
        <div className="zip-options">
          <label className="checkbox">
            <input
              type="checkbox"
              checked={zipOptions.webp}
              onChange={() => handleZipOptionToggle('webp')}
            />
            {t.zip.formats.webp}
          </label>
          <label className="checkbox">
            <input type="checkbox" checked={zipOptions.gif} onChange={() => handleZipOptionToggle('gif')} />
            {t.zip.formats.gif}
          </label>
          <label className="checkbox">
            <input type="checkbox" checked={zipOptions.dat} onChange={() => handleZipOptionToggle('dat')} />
            {t.zip.formats.dat}
          </label>
        </div>
        <div className="zip-bar">
          <div className="zip-summary">
            <div className="zip-message">
              {!selectionCount ?
                t.zip.summaryNeedSelection :
                !zipTypesSelected ?
                  t.zip.summaryNeedFormat :
                  t.zip.summaryReady(selectionCount, selectedZipFormats, MAX_ITEMS)}
            </div>
            {zipStatusText && <div className="zip-progress">{zipStatusText}</div>}
            {zipCacheMeta && <div className="zip-cache-note">{t.zip.cacheLabel(zipCacheMeta.filename)}</div>}
          </div>
          <div className="zip-buttons">
            <button onClick={handleZipDownload} disabled={!selectionCount || isZipping || !zipTypesSelected}>
              {isZipping ? t.buttons.loading : t.buttons.buildZip}
            </button>
            <button type="button" onClick={handleDownloadCachedZip} disabled={!zipCacheMeta}>
              {t.buttons.downloadZip}
            </button>
          </div>
        </div>
      </section>

      <footer className="page-footer">{t.header.footer}</footer>
    </div>
  );
}

export default App;
