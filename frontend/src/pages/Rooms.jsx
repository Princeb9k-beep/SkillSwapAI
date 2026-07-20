// Video Practice Rooms (spec §2.3).
//
// The lobby lists/creates rooms via REST. Joining opens a WebRTC mesh: each peer
// streams directly to every other peer, with the backend acting only as a signaling
// relay (SDP/ICE exchange) plus chat + shared-notes fan-out. A public STUN server is
// used for NAT traversal; a TURN server is required for reliable connectivity across
// restrictive networks in production.

import { useCallback, useEffect, useRef, useState } from "react";
import { api, roomSocketUrl } from "../api/client.js";
import { useApp } from "../context/AppContext.jsx";
import { ErrorBanner, EmptyState } from "../components/States.jsx";
import { SkeletonPage } from "../components/Skeleton.jsx";

const ICE_SERVERS = [{ urls: "stun:stun.l.google.com:19302" }];

function Lobby({ onEnter }) {
  const { notify } = useApp();
  const [rooms, setRooms] = useState([]);
  const [status, setStatus] = useState("loading");
  const [error, setError] = useState(null);
  const [title, setTitle] = useState("");
  const [topic, setTopic] = useState("General");
  const [creating, setCreating] = useState(false);

  const load = useCallback(async () => {
    setStatus("loading");
    try {
      setRooms(await api.listRooms());
      setStatus("ready");
    } catch (err) {
      setError(err.message);
      setStatus("error");
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function create(e) {
    e.preventDefault();
    setCreating(true);
    try {
      const room = await api.createRoom({ title, topic });
      notify("Room created", "success");
      onEnter(room);
    } catch (err) {
      notify(err.message, "error");
    } finally {
      setCreating(false);
    }
  }

  if (status === "loading") return <SkeletonPage />;
  if (status === "error") return <ErrorBanner message={error} onRetry={load} />;

  return (
    <section>
      <h1>Practice Rooms</h1>
      <p className="muted">
        Jump into a live video room to practice with a partner — mock interviews,
        pair programming, language exchange. Bring your camera.
      </p>

      <form className="card form" onSubmit={create}>
        <h3>Start a room</h3>
        <label>
          Title
          <input
            required
            maxLength={120}
            value={title}
            placeholder="e.g. Mock interview practice"
            onChange={(e) => setTitle(e.target.value)}
          />
        </label>
        <label>
          Topic
          <input
            maxLength={60}
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
          />
        </label>
        <button className="btn btn-primary" disabled={creating || !title.trim()} aria-busy={creating}>
          {creating ? "Creating…" : "Create room"}
        </button>
      </form>

      <div className="row-between">
        <h3>Open rooms</h3>
        <button type="button" className="btn" onClick={load}>
          Refresh
        </button>
      </div>
      {rooms.length === 0 ? (
        <EmptyState title="No open rooms" hint="Create one above to get started." />
      ) : (
        <div className="grid">
          {rooms.map((r) => (
            <div key={r.id} className="card">
              <div className="row-between">
                <h3>{r.title}</h3>
                <span className="pill">{r.topic}</span>
              </div>
              <p className="muted">
                Hosted by {r.host_name} · {r.live_count} live
              </p>
              <button className="btn btn-primary" onClick={() => onEnter(r)}>
                Join room
              </button>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function RemoteVideo({ stream, name }) {
  const ref = useRef(null);
  useEffect(() => {
    if (ref.current && stream) ref.current.srcObject = stream;
  }, [stream]);
  return (
    <div className="video-tile">
      <video ref={ref} autoPlay playsInline />
      <span className="video-name">{name}</span>
    </div>
  );
}

function Room({ room, onLeave }) {
  const { notify, user } = useApp();
  const localRef = useRef(null);
  const wsRef = useRef(null);
  const pcsRef = useRef(new Map()); // peer_id -> RTCPeerConnection
  const localStreamRef = useRef(null);
  const namesRef = useRef(new Map()); // peer_id -> display name

  const [remotes, setRemotes] = useState({}); // peer_id -> { stream, name }
  const [chat, setChat] = useState([]);
  const [message, setMessage] = useState("");
  const [notes, setNotes] = useState(room.notes || "");
  const [status, setStatus] = useState("connecting"); // connecting | live | error
  const [error, setError] = useState(null);
  const [muted, setMuted] = useState(false);
  const [camOff, setCamOff] = useState(false);

  const send = useCallback((obj) => {
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(obj));
  }, []);

  const setRemoteStream = useCallback((peerId, stream) => {
    setRemotes((prev) => ({
      ...prev,
      [peerId]: { stream, name: namesRef.current.get(peerId) || "Guest" },
    }));
  }, []);

  const createPeer = useCallback(
    (peerId) => {
      let pc = pcsRef.current.get(peerId);
      if (pc) return pc;
      pc = new RTCPeerConnection({ iceServers: ICE_SERVERS });
      pcsRef.current.set(peerId, pc);
      const local = localStreamRef.current;
      if (local) local.getTracks().forEach((t) => pc.addTrack(t, local));
      pc.onicecandidate = (e) => {
        if (e.candidate) send({ type: "signal", to: peerId, data: { candidate: e.candidate } });
      };
      pc.ontrack = (e) => setRemoteStream(peerId, e.streams[0]);
      return pc;
    },
    [send, setRemoteStream],
  );

  const dropPeer = useCallback((peerId) => {
    const pc = pcsRef.current.get(peerId);
    if (pc) {
      pc.close();
      pcsRef.current.delete(peerId);
    }
    namesRef.current.delete(peerId);
    setRemotes((prev) => {
      const next = { ...prev };
      delete next[peerId];
      return next;
    });
  }, []);

  useEffect(() => {
    let cancelled = false;
    const pcs = pcsRef.current;

    async function start() {
      let stream;
      try {
        stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
      } catch {
        if (!cancelled) {
          setError("Camera/microphone access is required to join a room.");
          setStatus("error");
        }
        return;
      }
      if (cancelled) {
        stream.getTracks().forEach((t) => t.stop());
        return;
      }
      localStreamRef.current = stream;
      if (localRef.current) localRef.current.srcObject = stream;

      const ws = new WebSocket(roomSocketUrl(room.code));
      wsRef.current = ws;

      ws.onopen = () => !cancelled && setStatus("live");
      ws.onerror = () => {
        if (!cancelled) {
          setError("Lost connection to the room.");
          setStatus("error");
        }
      };
      ws.onmessage = async (evt) => {
        const msg = JSON.parse(evt.data);
        if (msg.type === "welcome") {
          // We're the newcomer: offer to everyone already here.
          for (const peer of msg.peers) {
            namesRef.current.set(peer.peer_id, peer.name);
            const pc = createPeer(peer.peer_id);
            const offer = await pc.createOffer();
            await pc.setLocalDescription(offer);
            send({ type: "signal", to: peer.peer_id, data: { sdp: pc.localDescription } });
          }
        } else if (msg.type === "peer-joined") {
          namesRef.current.set(msg.peer_id, msg.name);
          // They will send us an offer; nothing to do yet.
        } else if (msg.type === "signal") {
          const pc = createPeer(msg.from);
          const { sdp, candidate } = msg.data || {};
          if (sdp) {
            await pc.setRemoteDescription(new RTCSessionDescription(sdp));
            if (sdp.type === "offer") {
              const answer = await pc.createAnswer();
              await pc.setLocalDescription(answer);
              send({ type: "signal", to: msg.from, data: { sdp: pc.localDescription } });
            }
          } else if (candidate) {
            try {
              await pc.addIceCandidate(new RTCIceCandidate(candidate));
            } catch {
              /* ignore late/duplicate candidates */
            }
          }
        } else if (msg.type === "peer-left") {
          dropPeer(msg.peer_id);
        } else if (msg.type === "chat") {
          setChat((c) => [...c, { from: msg.name, text: msg.text }]);
        } else if (msg.type === "notes") {
          setNotes(msg.text);
        } else if (msg.type === "error") {
          setError(msg.message || "Room unavailable.");
          setStatus("error");
        }
      };
    }

    start();

    return () => {
      cancelled = true;
      if (wsRef.current) wsRef.current.close();
      pcs.forEach((pc) => pc.close());
      pcs.clear();
      if (localStreamRef.current) localStreamRef.current.getTracks().forEach((t) => t.stop());
    };
  }, [room.code, createPeer, dropPeer, send]);

  function sendChat(e) {
    e.preventDefault();
    if (!message.trim()) return;
    send({ type: "chat", text: message });
    setChat((c) => [...c, { from: "You", text: message }]);
    setMessage("");
  }

  function onNotesChange(e) {
    setNotes(e.target.value);
    send({ type: "notes", text: e.target.value });
  }

  async function persistNotes() {
    try {
      await api.saveRoomNotes(room.code, notes);
      notify("Notes saved", "success");
    } catch (err) {
      notify(err.message, "error");
    }
  }

  function toggleMute() {
    const stream = localStreamRef.current;
    if (!stream) return;
    const enabled = !muted;
    stream.getAudioTracks().forEach((t) => (t.enabled = !enabled));
    setMuted(enabled);
  }

  function toggleCam() {
    const stream = localStreamRef.current;
    if (!stream) return;
    const off = !camOff;
    stream.getVideoTracks().forEach((t) => (t.enabled = !off));
    setCamOff(off);
  }

  async function shareScreen() {
    try {
      const display = await navigator.mediaDevices.getDisplayMedia({ video: true });
      const screenTrack = display.getVideoTracks()[0];
      pcsRef.current.forEach((pc) => {
        const sender = pc.getSenders().find((s) => s.track && s.track.kind === "video");
        if (sender) sender.replaceTrack(screenTrack);
      });
      if (localRef.current) localRef.current.srcObject = display;
      screenTrack.onended = () => {
        const cam = localStreamRef.current?.getVideoTracks()[0];
        pcsRef.current.forEach((pc) => {
          const sender = pc.getSenders().find((s) => s.track && s.track.kind === "video");
          if (sender && cam) sender.replaceTrack(cam);
        });
        if (localRef.current) localRef.current.srcObject = localStreamRef.current;
      };
    } catch {
      /* user cancelled the screen picker */
    }
  }

  async function leave() {
    if (room.host_id === user?.id) {
      try {
        await api.closeRoom(room.code);
      } catch {
        /* non-fatal */
      }
    }
    onLeave();
  }

  if (status === "error") {
    return (
      <section>
        <ErrorBanner message={error || "Couldn't join the room."} />
        <button className="btn" onClick={onLeave}>
          Back to lobby
        </button>
      </section>
    );
  }

  const remoteList = Object.entries(remotes);

  return (
    <section className="room">
      <div className="row-between">
        <div>
          <h1>{room.title}</h1>
          <p className="muted">
            {status === "connecting" ? "Connecting…" : "Live"} · Share code{" "}
            <code>{room.code}</code>
          </p>
        </div>
        <button className="btn btn-danger" onClick={leave}>
          {room.host_id === user?.id ? "End room" : "Leave"}
        </button>
      </div>

      <div className="video-grid">
        <div className="video-tile">
          <video ref={localRef} autoPlay playsInline muted />
          <span className="video-name">You{camOff ? " (camera off)" : ""}</span>
        </div>
        {remoteList.map(([peerId, r]) => (
          <RemoteVideo key={peerId} stream={r.stream} name={r.name} />
        ))}
      </div>
      {remoteList.length === 0 && (
        <p className="muted">Waiting for someone to join… share the code above.</p>
      )}

      <div className="room-controls">
        <button className="btn" onClick={toggleMute}>
          {muted ? "Unmute" : "Mute"}
        </button>
        <button className="btn" onClick={toggleCam}>
          {camOff ? "Camera on" : "Camera off"}
        </button>
        <button className="btn" onClick={shareScreen}>
          Share screen
        </button>
      </div>

      <div className="room-panels">
        <div className="card">
          <h3>Shared notes</h3>
          <textarea
            rows={6}
            value={notes}
            onChange={onNotesChange}
            placeholder="Collaborative scratchpad — everyone sees this live."
          />
          <button className="btn" onClick={persistNotes}>
            Save notes
          </button>
        </div>

        <div className="card chat">
          <h3>Chat</h3>
          <div className="chat-log">
            {chat.length === 0 ? (
              <p className="muted">No messages yet.</p>
            ) : (
              chat.map((m, i) => (
                <p key={i}>
                  <strong>{m.from}:</strong> {m.text}
                </p>
              ))
            )}
          </div>
          <form className="chat-input" onSubmit={sendChat}>
            <input
              value={message}
              placeholder="Message…"
              onChange={(e) => setMessage(e.target.value)}
            />
            <button className="btn btn-primary" disabled={!message.trim()}>
              Send
            </button>
          </form>
        </div>
      </div>
    </section>
  );
}

export default function Rooms() {
  const [active, setActive] = useState(null);
  return active ? (
    <Room room={active} onLeave={() => setActive(null)} />
  ) : (
    <Lobby onEnter={setActive} />
  );
}
