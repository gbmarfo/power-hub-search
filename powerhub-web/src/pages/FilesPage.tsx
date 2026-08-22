import { FormEvent, useCallback, useEffect, useState } from "react";
import { api, getToken } from "../api/client";
import { useAuth } from "../context/AuthContext";

export function FilesPage() {
  const { can } = useAuth();
  const [folderId, setFolderId] = useState<string | null>(null);
  const [listing, setListing] = useState<any>(null);
  const [error, setError] = useState("");
  const [showNewFolder, setShowNewFolder] = useState(false);
  const [folderName, setFolderName] = useState("");
  const [shareTarget, setShareTarget] = useState<{ type: string; id: string; name: string } | null>(null);
  const [contextMenu, setContextMenu] = useState<{ x: number; y: number; item: any; type: string } | null>(null);

  const load = useCallback(async () => {
    try {
      const data = await api.library(folderId);
      setListing(data);
      setError("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load library");
    }
  }, [folderId]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    const close = () => setContextMenu(null);
    window.addEventListener("click", close);
    return () => window.removeEventListener("click", close);
  }, []);

  async function createFolder(e: FormEvent) {
    e.preventDefault();
    await api.createFolder(folderName, folderId);
    setFolderName("");
    setShowNewFolder(false);
    await load();
  }

  async function onUpload(files: FileList | null) {
    if (!files?.length) return;
    for (const file of Array.from(files)) {
      await api.uploadFile(file, folderId);
    }
    await load();
  }

  async function createShare() {
    if (!shareTarget) return;
    const share = await api.createShare({
      item_type: shareTarget.type,
      item_id: shareTarget.id,
      role: "viewer",
    });
    await navigator.clipboard.writeText(`${window.location.origin}${share.url}`);
    setShareTarget(null);
    alert(`Share link copied:\n${window.location.origin}${share.url}`);
  }

  async function downloadFile(id: string, name: string) {
    const res = await fetch(api.downloadUrl(id), {
      headers: { Authorization: `Bearer ${getToken()}` },
    });
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = name;
    a.click();
    URL.revokeObjectURL(url);
  }

  if (!listing && !error) return <div className="muted">Loading files…</div>;

  return (
    <div onContextMenu={(e) => e.preventDefault()}>
      <h1 className="page-title">My Files</h1>
      <p className="page-sub">Upload, organize, share, and prepare documents for search indexing.</p>

      <div className="crumbs">
        <button type="button" onClick={() => setFolderId(null)}>Root</button>
        {(listing?.breadcrumbs || []).map((c: any) => (
          <span key={c.id}>
            / <button type="button" onClick={() => setFolderId(c.id)}>{c.name}</button>
          </span>
        ))}
      </div>

      <div className="toolbar">
        {can("folders.create") && (
          <button className="btn primary" type="button" onClick={() => setShowNewFolder(true)}>
            New folder
          </button>
        )}
        {can("files.upload") && (
          <label className="btn">
            Upload
            <input
              type="file"
              multiple
              hidden
              onChange={(e) => void onUpload(e.target.files)}
            />
          </label>
        )}
        <button className="btn ghost" type="button" onClick={() => void load()}>Refresh</button>
      </div>

      {error && <div className="error">{error}</div>}

      <div className="panel">
        <table className="table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Modified</th>
              <th>Size</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {(listing?.folders || []).map((folder: any) => (
              <tr
                key={folder.id}
                onDoubleClick={() => setFolderId(folder.id)}
                onContextMenu={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  setContextMenu({ x: e.clientX, y: e.clientY, item: folder, type: "folder" });
                }}
              >
                <td>
                  <button className="btn ghost" type="button" onClick={() => setFolderId(folder.id)}>
                    📁 {folder.name}
                  </button>
                </td>
                <td className="muted">{folder.updated_at ? new Date(folder.updated_at).toLocaleString() : "—"}</td>
                <td className="muted">—</td>
                <td>
                  <button className="btn" type="button" onClick={() => setShareTarget({ type: "folder", id: folder.id, name: folder.name })}>
                    Share
                  </button>
                </td>
              </tr>
            ))}
            {(listing?.files || []).map((file: any) => (
              <tr
                key={file.id}
                onContextMenu={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  setContextMenu({ x: e.clientX, y: e.clientY, item: file, type: "file" });
                }}
              >
                <td>
                  {file.starred ? "★ " : ""}📄 {file.name}
                </td>
                <td className="muted">{file.updated_at ? new Date(file.updated_at).toLocaleString() : "—"}</td>
                <td className="muted">{(file.size_bytes / 1024).toFixed(1)} KB</td>
                <td className="actions">
                  <button className="btn" type="button" onClick={() => void downloadFile(file.id, file.name)}>Download</button>
                  <button className="btn" type="button" onClick={() => setShareTarget({ type: "file", id: file.id, name: file.name })}>Share</button>
                  <button className="btn" type="button" onClick={() => void api.starFile(file.id).then(load)}>Star</button>
                </td>
              </tr>
            ))}
            {!listing?.folders?.length && !listing?.files?.length && (
              <tr>
                <td colSpan={4} className="empty">This folder is empty. Create a folder or upload files.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {showNewFolder && (
        <div className="modal-backdrop">
          <form className="modal" onSubmit={createFolder}>
            <h3>New folder</h3>
            <div className="field">
              <label>Name</label>
              <input value={folderName} onChange={(e) => setFolderName(e.target.value)} required autoFocus />
            </div>
            <div className="actions">
              <button className="btn primary" type="submit">Create</button>
              <button className="btn ghost" type="button" onClick={() => setShowNewFolder(false)}>Cancel</button>
            </div>
          </form>
        </div>
      )}

      {shareTarget && (
        <div className="modal-backdrop">
          <div className="modal">
            <h3>Share “{shareTarget.name}”</h3>
            <p className="muted">Create a link anyone can open without signing in.</p>
            <div className="actions">
              <button className="btn primary" type="button" onClick={() => void createShare()}>
                Create & copy link
              </button>
              <button className="btn ghost" type="button" onClick={() => setShareTarget(null)}>Cancel</button>
            </div>
          </div>
        </div>
      )}

      {contextMenu && (
        <div
          className="panel"
          style={{
            position: "fixed",
            left: contextMenu.x,
            top: contextMenu.y,
            zIndex: 50,
            padding: 8,
            minWidth: 180,
          }}
          onClick={(e) => e.stopPropagation()}
        >
          {contextMenu.type === "file" && (
            <>
              <button className="btn" style={{ width: "100%", marginBottom: 4 }} type="button" onClick={() => void downloadFile(contextMenu.item.id, contextMenu.item.name)}>Download</button>
              <button className="btn" style={{ width: "100%", marginBottom: 4 }} type="button" onClick={() => { setShareTarget({ type: "file", id: contextMenu.item.id, name: contextMenu.item.name }); setContextMenu(null); }}>Share</button>
              <button className="btn" style={{ width: "100%", marginBottom: 4 }} type="button" onClick={() => {
                const name = prompt("Rename file", contextMenu.item.name);
                if (name) void api.renameFile(contextMenu.item.id, name).then(load);
                setContextMenu(null);
              }}>Rename</button>
              <button className="btn danger" style={{ width: "100%" }} type="button" onClick={() => void api.deleteFile(contextMenu.item.id).then(load)}>Delete</button>
            </>
          )}
          {contextMenu.type === "folder" && (
            <>
              <button className="btn" style={{ width: "100%", marginBottom: 4 }} type="button" onClick={() => { setFolderId(contextMenu.item.id); setContextMenu(null); }}>Open</button>
              <button className="btn" style={{ width: "100%", marginBottom: 4 }} type="button" onClick={() => { setShareTarget({ type: "folder", id: contextMenu.item.id, name: contextMenu.item.name }); setContextMenu(null); }}>Share</button>
              <button className="btn danger" style={{ width: "100%" }} type="button" onClick={() => void api.deleteFolder(contextMenu.item.id).then(load)}>Delete</button>
            </>
          )}
        </div>
      )}
    </div>
  );
}
