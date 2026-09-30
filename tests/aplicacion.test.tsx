import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { cleanup, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { App } from '../src/App';

function abrirApp() {
  window.location.hash = '#/';
  return render(<App />);
}

beforeEach(() => {
  window.localStorage.clear();
});

afterEach(() => {
  cleanup();
});

describe('flujo completo de la aplicacion', () => {
  it('carga un caso de ejemplo y arma todos los reportes', async () => {
    const usuario = userEvent.setup();
    abrirApp();

    await screen.findByText('Bienvenido a ContaSys');

    await usuario.click(screen.getByRole('link', { name: 'Casos' }));
    const tarjetaDemo = await screen.findByText('CYBERTEC S.A.');
    const fila = tarjetaDemo.closest('.acceso');
    expect(fila).not.toBeNull();
    await usuario.click(within(fila as HTMLElement).getByRole('button', { name: 'Cargar' }));

    // El caso abre directamente en el libro diario.
    await screen.findByRole('heading', { name: 'Libro Diario', level: 2 });
    expect(await screen.findByText(/Asiento #1/)).toBeInTheDocument();
    expect(screen.getByText(/Asiento #4/)).toBeInTheDocument();

    await usuario.click(screen.getByRole('link', { name: 'Balance de Comprobación' }));
    await waitFor(() =>
      expect(screen.getByText(/Balance cuadrado/i)).toBeInTheDocument(),
    );
    expect(screen.getAllByText('S/ 100,000.00').length).toBeGreaterThan(0);

    await usuario.click(screen.getByRole('link', { name: 'Estado de Resultados' }));
    await screen.findByText('Estado de resultados por naturaleza');
    expect(screen.getAllByText('S/ 10,000.00').length).toBeGreaterThan(0);

    await usuario.click(screen.getByRole('link', { name: 'Balance General' }));
    await screen.findByText('Comprobación de la ecuación contable');
    expect(screen.getByText(/Sí cumple/i)).toBeInTheDocument();
  }, 30000);

  it('no deja registrar un asiento descuadrado y sí uno cuadrado', async () => {
    const usuario = userEvent.setup();
    abrirApp();

    await screen.findByText('Bienvenido a ContaSys');
    await usuario.click(screen.getByRole('link', { name: 'Casos' }));
    const tarjetaDemo = await screen.findByText('Comercializadora Metropolitana');
    const fila = tarjetaDemo.closest('.acceso');
    await usuario.click(within(fila as HTMLElement).getByRole('button', { name: 'Cargar' }));
    await screen.findByRole('heading', { name: 'Libro Diario', level: 2 });

    await usuario.click(screen.getByRole('link', { name: 'Registrar Asiento' }));
    await screen.findByText('Movimientos del asiento');

    const cuentas = screen.getAllByLabelText('Cuenta');
    await usuario.selectOptions(cuentas[0], within(cuentas[0]).getByRole('option', { name: /101 — Caja/ }));
    await usuario.selectOptions(cuentas[1], within(cuentas[1]).getByRole('option', { name: /301 — Capital/ }));

    const debes = screen.getAllByLabelText('Importe al Debe');
    const haberes = screen.getAllByLabelText('Importe al Haber');
    await usuario.type(debes[0], '500');
    await usuario.type(haberes[1], '300');

    await usuario.click(screen.getByRole('button', { name: 'Registrar asiento' }));
    expect(await screen.findByText(/no cuadra. Diferencia de 200.00/i)).toBeInTheDocument();

    await usuario.clear(haberes[1]);
    await usuario.type(haberes[1], '500');
    await usuario.click(screen.getByRole('button', { name: 'Registrar asiento' }));

    await waitFor(() => expect(screen.getByText('Asiento registrado.')).toBeInTheDocument());
  }, 30000);

  it('guarda el caso en el navegador y lo recupera al volver a abrir', async () => {
    const usuario = userEvent.setup();
    const primera = abrirApp();

    await screen.findByText('Bienvenido a ContaSys');
    await usuario.click(screen.getByRole('link', { name: 'Casos' }));
    const tarjetaDemo = await screen.findByText('CYBERTEC S.A.');
    await usuario.click(
      within(tarjetaDemo.closest('.acceso') as HTMLElement).getByRole('button', { name: 'Cargar' }),
    );
    await screen.findByRole('heading', { name: 'Libro Diario', level: 2 });

    await waitFor(() => expect(window.localStorage.getItem('contasys:estado')).toBeTruthy());
    primera.unmount();
    cleanup();

    abrirApp();
    expect((await screen.findAllByText('CYBERTEC S.A.')).length).toBeGreaterThan(0);
  }, 30000);
});
