import type { ReactNode } from 'react';
import { HashRouter, Navigate, Route, Routes } from 'react-router-dom';
import { ProveedorAlmacen } from './almacen/almacen';
import { ProveedorAvisos } from './componentes/Avisos';
import { Layout, RequiereCaso } from './componentes/Layout';
import { Inicio } from './paginas/Inicio';
import { Casos } from './paginas/Casos';
import { PlanCuentas } from './paginas/PlanCuentas';
import { RegistrarAsiento } from './paginas/RegistrarAsiento';
import { LibroDiario } from './paginas/LibroDiario';
import { LibroMayor } from './paginas/LibroMayor';
import { BalanceComprobacion } from './paginas/BalanceComprobacion';
import { EstadoResultados } from './paginas/EstadoResultados';
import { BalanceGeneral } from './paginas/BalanceGeneral';
import { ReportePdf } from './paginas/ReportePdf';
import { Configuracion } from './paginas/Configuracion';

/** Envuelve una pantalla que necesita un caso abierto. */
function ConCaso({ children }: { children: ReactNode }) {
  return <RequiereCaso>{children}</RequiereCaso>;
}

export function App() {
  return (
    <ProveedorAlmacen>
      <ProveedorAvisos>
        <HashRouter>
          <Routes>
            <Route element={<Layout />}>
              <Route index element={<Inicio />} />
              <Route path="casos" element={<Casos />} />
              <Route
                path="plan-de-cuentas"
                element={
                  <ConCaso>
                    <PlanCuentas />
                  </ConCaso>
                }
              />
              <Route
                path="asientos"
                element={
                  <ConCaso>
                    <RegistrarAsiento />
                  </ConCaso>
                }
              />
              <Route
                path="asientos/:id"
                element={
                  <ConCaso>
                    <RegistrarAsiento />
                  </ConCaso>
                }
              />
              <Route
                path="libro-diario"
                element={
                  <ConCaso>
                    <LibroDiario />
                  </ConCaso>
                }
              />
              <Route
                path="libro-mayor"
                element={
                  <ConCaso>
                    <LibroMayor />
                  </ConCaso>
                }
              />
              <Route
                path="balance-comprobacion"
                element={
                  <ConCaso>
                    <BalanceComprobacion />
                  </ConCaso>
                }
              />
              <Route
                path="estado-resultados"
                element={
                  <ConCaso>
                    <EstadoResultados />
                  </ConCaso>
                }
              />
              <Route
                path="balance-general"
                element={
                  <ConCaso>
                    <BalanceGeneral />
                  </ConCaso>
                }
              />
              <Route
                path="reporte"
                element={
                  <ConCaso>
                    <ReportePdf />
                  </ConCaso>
                }
              />
              <Route
                path="configuracion"
                element={
                  <ConCaso>
                    <Configuracion />
                  </ConCaso>
                }
              />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Route>
          </Routes>
        </HashRouter>
      </ProveedorAvisos>
    </ProveedorAlmacen>
  );
}

export default App;
