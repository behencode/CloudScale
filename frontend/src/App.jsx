import { BrowserRouter, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./auth";
import { RequireAuth } from "./guards";
import { Browse, Dashboard, Detail, Editor, Landing, Layout, Login, NotFound, Profile, Register } from "./pages";

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Layout>
          <Routes>
            <Route path="/" element={<Landing />} />
            <Route path="/login" element={<Login />} />
            <Route path="/register" element={<Register />} />
            <Route path="/browse" element={<Browse />} />
            <Route path="/listings/:id" element={<Detail />} />
            <Route path="/listings/:id/edit" element={<RequireAuth><Editor mode="edit" /></RequireAuth>} />
            <Route path="/create" element={<RequireAuth><Editor mode="create" /></RequireAuth>} />
            <Route path="/dashboard" element={<RequireAuth><Dashboard /></RequireAuth>} />
            <Route path="/profile" element={<RequireAuth><Profile /></RequireAuth>} />
            <Route path="*" element={<NotFound />} />
          </Routes>
        </Layout>
      </BrowserRouter>
    </AuthProvider>
  );
}
