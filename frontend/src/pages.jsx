import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, cognitoConfirmSignUp, cognitoLogin, cognitoSignUp } from "./api";
import { useAuth } from "./auth";

const EMPTY_LISTING = {
  title: "",
  description: "",
  category: "community",
  intent: "offer",
  location: "",
  contact: "",
  image_key: "",
  image_url: "",
  clear_image: false,
  description_source: "user",
  category_source: "user",
};

const FALLBACK_INTENTS = ["lost", "found", "offer", "request"];

function labelize(value) {
  return String(value).replace(/-/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatWhen(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

export function Layout({ children }) {
  const { user, logout } = useAuth();
  const [health, setHealth] = useState(null);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    api("/api/health").then(setHealth).catch(() => setHealth(null));
  }, []);

  return (
    <>
      <a className="skip" href="#content">Skip to content</a>
      <header className="topbar">
        <Link className="brand" to="/" onClick={() => setOpen(false)}>
          <span>CloudScale</span>
          CampusConnect
        </Link>
        <button className="menu" type="button" aria-expanded={open} onClick={() => setOpen((value) => !value)}>
          Menu
        </button>
        <nav className={open ? "open" : ""}>
          <Link to="/browse" onClick={() => setOpen(false)}>Browse</Link>
          {user ? (
            <>
              <Link to="/dashboard" onClick={() => setOpen(false)}>Dashboard</Link>
              <Link to="/create" onClick={() => setOpen(false)}>New listing</Link>
              <Link to="/profile" onClick={() => setOpen(false)}>{user.name}</Link>
              <button type="button" onClick={() => { logout(); setOpen(false); }}>Sign out</button>
            </>
          ) : (
            <>
              <Link to="/login" onClick={() => setOpen(false)}>Sign in</Link>
              <Link className="button" to="/register" onClick={() => setOpen(false)}>Join</Link>
            </>
          )}
        </nav>
      </header>
      {health && (
        <p className="mode">
          Mode {health.app_mode}. Auth {health.auth_mode}. Data {health.database_backend}. Descriptions {health.description_provider}. Categories {health.category_provider}. Notifications {health.notification_backend}.
          {health.warnings.length > 0 ? ` Warning: ${health.warnings.join(" ")}` : ""}
        </p>
      )}
      <main id="content">{children}</main>
    </>
  );
}

export function Landing() {
  return (
    <section className="hero">
      <div>
        <p className="eyebrow">University community board</p>
        <h1>Share what your campus still needs a home for.</h1>
        <p className="lede">
          CampusConnect is the CloudScale semester project: lost-and-found posts, textbooks,
          rooms, events, and community offers, with local development that stays off AWS until you opt in.
        </p>
        <div className="actions">
          <Link className="button" to="/browse">Browse listings</Link>
          <Link className="button secondary" to="/register">Create an account</Link>
        </div>
      </div>
      <ul className="steps">
        <li><strong>1. Post</strong><span>Describe an item, a room, or something you found.</span></li>
        <li><strong>2. Classify</strong><span>Use the local classifier, or SageMaker when that mode is configured.</span></li>
        <li><strong>3. Describe</strong><span>Draft the wording yourself, or ask Amazon Bedrock in AWS mode.</span></li>
        <li><strong>4. Notify</strong><span>Local mode stores a notice. AWS mode uses SQS, Lambda, and SNS.</span></li>
      </ul>
    </section>
  );
}

export function Login() {
  const navigate = useNavigate();
  const { setSession } = useAuth();
  const [health, setHealth] = useState(null);
  const [healthReady, setHealthReady] = useState(false);
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);

  useEffect(() => {
    api("/api/health")
      .then(setHealth)
      .catch((err) => setError(err.message))
      .finally(() => setHealthReady(true));
  }, []);

  async function onSubmit(event) {
    event.preventDefault();
    if (!health) return;
    setError("");
    setPending(true);
    const form = new FormData(event.target);
    const email = String(form.get("email") || "");
    const password = String(form.get("password") || "");
    try {
      if (health.auth_mode === "cognito") {
        const token = await cognitoLogin(email, password);
        localStorage.setItem("cc_token", token);
        const user = await api("/api/auth/me");
        setSession(token, user);
      } else {
        const result = await api("/api/auth/login", { method: "POST", body: { email, password } });
        setSession(result.access_token, result.user);
      }
      navigate("/dashboard");
    } catch (err) {
      setError(err.message);
    } finally {
      setPending(false);
    }
  }

  const cognito = health && health.auth_mode === "cognito";
  return (
    <section className="panel narrow">
      <p className="eyebrow">{!healthReady ? "Checking sign-in mode" : cognito ? "Amazon Cognito" : "Local development sign-in"}</p>
      <h1>Sign in</h1>
      <p>
        {cognito
          ? "This server expects an Amazon Cognito ID token. The form calls Cognito directly and does not use the local password store."
          : "Passwords stay in the local SQLite database. Amazon Cognito is not contacted."}
      </p>
      <form onSubmit={onSubmit}>
        <label>Email<input name="email" type="email" autoComplete="username" required /></label>
        <label>Password<input name="password" type="password" autoComplete="current-password" required minLength={cognito ? 1 : 8} /></label>
        {error && <p className="error">{error}</p>}
        <button className="button" type="submit" disabled={pending || !health}>{pending ? "Signing in…" : "Sign in"}</button>
      </form>
      {!cognito && <p className="fine">No account yet? <Link to="/register">Register locally</Link>.</p>}
    </section>
  );
}

export function Register() {
  const navigate = useNavigate();
  const { setSession } = useAuth();
  const [health, setHealth] = useState(null);
  const [healthReady, setHealthReady] = useState(false);
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  const [cognitoStep, setCognitoStep] = useState("signup");

  useEffect(() => {
    api("/api/health")
      .then(setHealth)
      .catch((err) => setError(err.message))
      .finally(() => setHealthReady(true));
  }, []);

  async function onSubmit(event) {
    event.preventDefault();
    setPending(true);
    setError("");
    const form = new FormData(event.target);
    try {
      if (health?.auth_mode === "cognito") {
        const email = String(form.get("email") || "").trim().toLowerCase();
        if (cognitoStep === "confirm") {
          await cognitoConfirmSignUp(email, String(form.get("confirmation_code") || "").trim());
          navigate("/login", { state: { message: "Your email is confirmed. Sign in to continue." } });
        } else {
          const result = await cognitoSignUp({
            name: String(form.get("name") || "").trim(),
            email,
            password: String(form.get("password") || ""),
          });
          if (result.UserConfirmed) {
            navigate("/login", { state: { message: "Your account is ready. Sign in to continue." } });
          } else {
            setCognitoStep("confirm");
          }
        }
        return;
      }
      const result = await api("/api/auth/register", {
        method: "POST",
        body: {
          name: form.get("name"),
          email: form.get("email"),
          password: form.get("password"),
          campus: form.get("campus"),
        },
      });
      setSession(result.access_token, result.user);
      navigate("/dashboard");
    } catch (err) {
      setError(err.message);
    } finally {
      setPending(false);
    }
  }

  if (!healthReady) {
    return (
      <section className="panel narrow">
        <p className="status">Checking registration mode…</p>
      </section>
    );
  }

  const cognito = health?.auth_mode === "cognito";

  return (
    <section className="panel narrow">
      <p className="eyebrow">{cognito ? "Amazon Cognito" : "Local development account"}</p>
      <h1>{cognitoStep === "confirm" ? "Confirm your email" : "Join CampusConnect"}</h1>
      {cognito && <p>{cognitoStep === "confirm" ? "Enter the confirmation code sent to your email." : "Create an account in the configured Cognito user pool."}</p>}
      <form onSubmit={onSubmit}>
        {cognitoStep === "signup" && <label>Name<input name="name" required minLength={2} maxLength={80} /></label>}
        <label>Email<input name="email" type="email" required readOnly={cognitoStep === "confirm"} /></label>
        {!cognito && <label>Campus<input name="campus" maxLength={120} placeholder="North Campus" /></label>}
        {cognitoStep === "signup" && <label>Password<input name="password" type="password" required minLength={8} /></label>}
        {cognitoStep === "confirm" && <label>Confirmation code<input name="confirmation_code" autoComplete="one-time-code" required /></label>}
        {error && <p className="error">{error}</p>}
        <button className="button" type="submit" disabled={pending || !health}>{pending ? "Please wait…" : cognitoStep === "confirm" ? "Confirm account" : "Create account"}</button>
      </form>
    </section>
  );
}

export function Browse() {
  const [categories, setCategories] = useState([]);
  const [intents, setIntents] = useState(FALLBACK_INTENTS);
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("");
  const [intent, setIntent] = useState("");
  const [listings, setListings] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api("/api/categories")
      .then((data) => {
        setCategories(data.categories);
        if (Array.isArray(data.intents) && data.intents.length > 0) setIntents(data.intents);
      })
      .catch((err) => setError(err.message));
  }, []);

  useEffect(() => {
    const params = new URLSearchParams();
    if (query) params.set("q", query);
    if (category) params.set("category", category);
    if (intent) params.set("intent", intent);
    setListings(null);
    api(`/api/listings?${params.toString()}`)
      .then(setListings)
      .catch((err) => {
        setError(err.message);
        setListings([]);
      });
  }, [query, category, intent]);

  return (
    <section>
      <div className="section-head">
        <div>
          <p className="eyebrow">Public board</p>
          <h1>Browse listings</h1>
        </div>
      </div>
      <div className="filters">
        <label>Search<input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Keys, textbook, room" /></label>
        <label>Category
          <select value={category} onChange={(event) => setCategory(event.target.value)}>
            <option value="">All categories</option>
            {categories.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}
          </select>
        </label>
        <label>Intent
          <select value={intent} onChange={(event) => setIntent(event.target.value)}>
            <option value="">Any</option>
            {intents.map((item) => <option key={item} value={item}>{labelize(item)}</option>)}
          </select>
        </label>
      </div>
      {error && <p className="error">{error}</p>}
      {listings === null && <p className="status">Loading listings…</p>}
      {listings && listings.length === 0 && <p className="empty">No listings match this search.</p>}
      <div className="cards">
        {listings && listings.map((listing) => <ListingCard key={listing.id} listing={listing} />)}
      </div>
    </section>
  );
}

export function ListingCard({ listing }) {
  return (
    <article className="card">
      {listing.image_url ? <img src={listing.image_url} alt="" /> : <div className="placeholder">{listing.category}</div>}
      <div>
        <p className="meta">{listing.category} · {listing.intent} · {listing.status}</p>
        <h2><Link to={`/listings/${listing.id}`}>{listing.title}</Link></h2>
        <p>{listing.location || "Location not set"} · {listing.owner_name}</p>
      </div>
    </article>
  );
}

export function Detail() {
  const { id } = useParams();
  const { user } = useAuth();
  const navigate = useNavigate();
  const [listing, setListing] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api(`/api/listings/${id}`).then(setListing).catch((err) => setError(err.message));
  }, [id]);

  async function remove() {
    if (!window.confirm("Delete this listing?")) return;
    try {
      await api(`/api/listings/${id}`, { method: "DELETE" });
      navigate("/dashboard");
    } catch (err) {
      setError(err.message);
    }
  }

  if (error) return <p className="error">{error}</p>;
  if (!listing) return <p className="status">Loading listing…</p>;
  const mine = user && user.id === listing.owner_id;
  return (
    <article className="detail">
      {listing.image_url ? <img src={listing.image_url} alt={listing.title} /> : <div className="placeholder large">{listing.category}</div>}
      <div>
        <p className="meta">{listing.category} · {listing.intent} · {listing.status}</p>
        <h1>{listing.title}</h1>
        <p className="lede">{listing.description}</p>
        <dl>
          <div><dt>Posted by</dt><dd>{listing.owner_name}</dd></div>
          <div><dt>Location</dt><dd>{listing.location || "Not set"}</dd></div>
          <div><dt>Contact</dt><dd>{listing.contact || "Not set"}</dd></div>
          <div><dt>Updated</dt><dd>{formatWhen(listing.updated_at)}</dd></div>
          <div><dt>Description source</dt><dd>{listing.description_source}</dd></div>
          <div><dt>Category source</dt><dd>{listing.category_source}</dd></div>
        </dl>
        {mine && (
          <div className="actions">
            <Link className="button" to={`/listings/${listing.id}/edit`}>Edit</Link>
            <button className="button secondary" type="button" onClick={remove}>Delete</button>
          </div>
        )}
      </div>
    </article>
  );
}

export function Editor({ mode }) {
  const { id } = useParams();
  const navigate = useNavigate();
  const [form, setForm] = useState(EMPTY_LISTING);
  const [categories, setCategories] = useState([]);
  const [intents, setIntents] = useState(FALLBACK_INTENTS);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  const [loaded, setLoaded] = useState(mode === "create");

  useEffect(() => {
    api("/api/categories")
      .then((data) => {
        setCategories(data.categories);
        if (Array.isArray(data.intents) && data.intents.length > 0) setIntents(data.intents);
      })
      .catch((err) => setError(err.message));
    if (mode === "edit") {
      api(`/api/listings/${id}`)
        .then((listing) => {
          setForm({
            title: listing.title,
            description: listing.description,
            category: listing.category,
            intent: listing.intent,
            location: listing.location,
            contact: listing.contact,
            image_key: listing.image_key || "",
            image_url: listing.image_url || "",
            clear_image: false,
            status: listing.status,
            description_source: listing.description_source,
            category_source: listing.category_source,
          });
          setLoaded(true);
        })
        .catch((err) => setError(err.message));
    }
  }, [id, mode]);

  function update(event) {
    setForm((current) => ({ ...current, [event.target.name]: event.target.value }));
  }

  async function assistDescription() {
    setError("");
    setNotice("");
    try {
      const result = await api("/api/listings/assist/description", {
        method: "POST",
        body: { title: form.title, category: form.category, details: form.description },
      });
      setForm((current) => ({ ...current, description: result.description, description_source: result.provider }));
      setNotice(result.notice);
    } catch (err) {
      setError(err.message);
    }
  }

  async function assistCategory() {
    setError("");
    setNotice("");
    try {
      const result = await api("/api/listings/assist/category", {
        method: "POST",
        body: { title: form.title, details: form.description },
      });
      setForm((current) => ({ ...current, category: result.category, category_source: result.provider }));
      setNotice(`${result.notice} Confidence ${result.confidence}.`);
    } catch (err) {
      setError(err.message);
    }
  }

  async function onFile(event) {
    const file = event.target.files && event.target.files[0];
    if (!file) return;
    setError("");
    const body = new FormData();
    body.append("file", file);
    try {
      const uploaded = await api("/api/uploads", { method: "POST", body });
      setForm((current) => ({
        ...current,
        image_key: uploaded.image_key,
        image_url: uploaded.image_url,
        clear_image: false,
      }));
    } catch (err) {
      setError(err.message);
    }
  }

  async function onSubmit(event) {
    event.preventDefault();
    setPending(true);
    setError("");
    const payload = {
      title: form.title,
      description: form.description,
      category: form.category,
      intent: form.intent,
      location: form.location,
      contact: form.contact,
      description_source: form.description_source,
      category_source: form.category_source,
    };
    if (form.image_key) payload.image_key = form.image_key;
    if (mode === "edit") {
      payload.status = form.status;
      if (form.clear_image && !form.image_key) payload.clear_image = true;
    }
    try {
      const result = mode === "create"
        ? await api("/api/listings", { method: "POST", body: payload })
        : await api(`/api/listings/${id}`, { method: "PATCH", body: payload });
      const listing = result.listing || result;
      if (result.notification_warning) {
        window.alert(`Listing saved. Notification delivery failed: ${result.notification_warning}`);
      }
      navigate(`/listings/${listing.id}`);
    } catch (err) {
      setError(err.message);
    } finally {
      setPending(false);
    }
  }

  if (!loaded) return <p className="status">Loading listing…</p>;
  return (
    <section className="panel">
      <p className="eyebrow">{mode === "create" ? "New listing" : "Edit listing"}</p>
      <h1>{mode === "create" ? "Post to the board" : "Update listing"}</h1>
      <form onSubmit={onSubmit} className="editor">
        <label>Title<input name="title" value={form.title} onChange={update} required minLength={3} maxLength={120} /></label>
        <div className="split">
          <label>Category
            <select name="category" value={form.category} onChange={update}>
              {categories.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}
            </select>
          </label>
          <label>Intent
            <select name="intent" value={form.intent} onChange={update}>
              {intents.map((item) => <option key={item} value={item}>{labelize(item)}</option>)}
            </select>
          </label>
        </div>
        <label>Description<textarea name="description" value={form.description} onChange={update} required minLength={10} rows={6} /></label>
        <div className="actions">
          <button className="button secondary" type="button" onClick={assistCategory}>Predict category</button>
          <button className="button secondary" type="button" onClick={assistDescription}>Generate description</button>
        </div>
        <label>Location<input name="location" value={form.location} onChange={update} maxLength={200} /></label>
        <label>Contact<input name="contact" value={form.contact} onChange={update} maxLength={200} /></label>
        <label>Photo<input type="file" accept="image/png,image/jpeg,image/webp,image/gif" onChange={onFile} /></label>
        {form.image_url && <img className="preview" src={form.image_url} alt="Uploaded listing" />}
        {(form.image_url || form.image_key) && (
          <button
            className="button secondary"
            type="button"
            onClick={() => setForm((current) => ({ ...current, image_key: "", image_url: "", clear_image: true }))}
          >
            Remove photo
          </button>
        )}
        {mode === "edit" && (
          <label>Status
            <select name="status" value={form.status} onChange={update}>
              <option value="open">Open</option>
              <option value="resolved">Resolved</option>
            </select>
          </label>
        )}
        {notice && <p className="notice">{notice}</p>}
        {error && <p className="error">{error}</p>}
        <button className="button" type="submit" disabled={pending}>{pending ? "Saving…" : "Save listing"}</button>
      </form>
    </section>
  );
}

export function Dashboard() {
  const { user } = useAuth();
  const [listings, setListings] = useState(null);
  const [notes, setNotes] = useState(null);
  const [error, setError] = useState("");

  function load() {
    Promise.all([api("/api/listings?mine=true"), api("/api/notifications")])
      .then(([mine, notifications]) => {
        setListings(mine);
        setNotes(notifications);
      })
      .catch((err) => setError(err.message));
  }

  useEffect(() => { load(); }, []);

  async function markRead(id) {
    try {
      await api(`/api/notifications/${id}/read`, { method: "POST" });
      load();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <section>
      <div className="section-head">
        <div>
          <p className="eyebrow">Your board</p>
          <h1>Hello, {user.name}</h1>
          <p>{user.campus || "Add a campus on your profile."}</p>
        </div>
        <Link className="button" to="/create">New listing</Link>
      </div>
      {error && <p className="error">{error}</p>}
      <div className="dashboard">
        <div>
          <h2>Your listings</h2>
          {listings === null && <p className="status">Loading your listings…</p>}
          {listings && listings.length === 0 && <p className="empty">You have not posted yet.</p>}
          <div className="cards">
            {listings && listings.map((listing) => <ListingCard key={listing.id} listing={listing} />)}
          </div>
        </div>
        <aside>
          <h2>Notifications</h2>
          {notes === null && <p className="status">Loading notifications…</p>}
          {notes && notes.length === 0 && <p className="empty">No notifications yet.</p>}
          <ul className="notes">
            {notes && notes.map((note) => (
              <li key={note.id} className={note.read ? "read" : ""}>
                <p>{note.message}</p>
                <span>{note.channel} · {formatWhen(note.created_at)}</span>
                {!note.read && <button type="button" onClick={() => markRead(note.id)}>Mark read</button>}
              </li>
            ))}
          </ul>
        </aside>
      </div>
    </section>
  );
}

export function Profile() {
  const { user, setSession } = useAuth();
  const [error, setError] = useState("");
  const [saved, setSaved] = useState("");

  async function onSubmit(event) {
    event.preventDefault();
    setError("");
    setSaved("");
    const form = new FormData(event.target);
    try {
      const updated = await api("/api/auth/me", {
        method: "PATCH",
        body: { name: form.get("name"), campus: form.get("campus"), bio: form.get("bio") },
      });
      const token = localStorage.getItem("cc_token");
      setSession(token, updated);
      setSaved("Profile saved.");
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <section className="panel narrow">
      <p className="eyebrow">Profile</p>
      <h1>{user.email}</h1>
      <form onSubmit={onSubmit}>
        <label>Name<input name="name" defaultValue={user.name} required minLength={2} /></label>
        <label>Campus<input name="campus" defaultValue={user.campus} /></label>
        <label>Bio<textarea name="bio" defaultValue={user.bio} rows={4} maxLength={500} /></label>
        {error && <p className="error">{error}</p>}
        {saved && <p className="notice">{saved}</p>}
        <button className="button" type="submit">Save profile</button>
      </form>
    </section>
  );
}

export function NotFound() {
  return (
    <section className="panel narrow">
      <h1>That page is not on the board.</h1>
      <Link className="button" to="/browse">Back to listings</Link>
    </section>
  );
}
