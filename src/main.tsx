import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { App } from './App';
import './estilos/global.css';

const contenedor = document.getElementById('root');
if (!contenedor) throw new Error('No se encontro el elemento #root en index.html.');

createRoot(contenedor).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
