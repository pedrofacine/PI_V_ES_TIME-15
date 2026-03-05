import { Outlet } from 'react-router-dom';
import { Header } from '../components/Header/Header';

export function MainLayout() {
  return (
    <div className="app-container">
        <Header/>
      <main className="content">
        <Outlet />
      </main>
    </div>
  );
}