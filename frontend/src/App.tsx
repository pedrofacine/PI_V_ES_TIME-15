import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { MainLayout } from "./layouts/MainLayout";
import { PrivateRoute } from "./components/PrivateRoute/PrivateRoute";

import Login from './pages/Login/Login';
import SignUp from './pages/SignUp/SignUp';
import ResetPassword from "./pages/resetPassword/resetPassword";
import InputPage from "./pages/input/input";
import JobContainerPage from './pages/JobContainerPage/JobContainer';
import ClipsHistory from './pages/clips-history/ClipsHistory';
import NewPassword from './pages/NewPassword/NewPassword';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>

        <Route path="/"          element={<Login />} />
        <Route path="/signup"         element={<SignUp />} />
        <Route path="/reset-password" element={<ResetPassword />} />
        <Route path="/new-password" element={<NewPassword />} />

        <Route element={<PrivateRoute />}>

          <Route element={<MainLayout />}>
            <Route path="/input"              element={<InputPage />} />
            <Route path="/clips-history" element={<ClipsHistory />} />
          </Route>

          <Route path="/processing-clips/:jobId" element={<MainLayout />}>
            <Route index element={<JobContainerPage />} />
          </Route>

        </Route>

        <Route path="*" element={<Navigate to="/" replace />} />

      </Routes>
    </BrowserRouter>
  );
}