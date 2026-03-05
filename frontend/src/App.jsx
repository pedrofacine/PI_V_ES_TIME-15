import { useState } from 'react';
import Login from './pages/Login/Login';
import SignUp from './pages/SignUp/SignUp';

export default function App() {
  const [currentPage, setCurrentPage] = useState('login');

  return (
    <>
      {currentPage === 'login' ? (
        <Login onSignUpClick={() => setCurrentPage('signup')} />
      ) : (
        <SignUp onLoginClick={() => setCurrentPage('login')} />
      )}
    </>
  );
}