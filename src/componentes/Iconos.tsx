import type { SVGProps } from 'react';

type Props = SVGProps<SVGSVGElement> & { tamano?: number };

function Base({ tamano = 18, children, ...resto }: Props & { children: React.ReactNode }) {
  return (
    <svg
      width={tamano}
      height={tamano}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      {...resto}
    >
      {children}
    </svg>
  );
}

export const IconoInicio = (p: Props) => (
  <Base {...p}>
    <path d="M3 10.5 12 3l9 7.5" />
    <path d="M5 9.5V20h14V9.5" />
    <path d="M9.5 20v-6h5v6" />
  </Base>
);

export const IconoPlan = (p: Props) => (
  <Base {...p}>
    <rect x="4" y="3" width="16" height="18" rx="2" />
    <path d="M8 7h8M8 12h8M8 17h5" />
  </Base>
);

export const IconoAsiento = (p: Props) => (
  <Base {...p}>
    <path d="M4 20h16" />
    <path d="m14.5 4.5 5 5L9 20H4v-5z" />
  </Base>
);

export const IconoDiario = (p: Props) => (
  <Base {...p}>
    <path d="M5 4h11a3 3 0 0 1 3 3v13H8a3 3 0 0 1-3-3z" />
    <path d="M5 17h11" />
    <path d="M9 8h6" />
  </Base>
);

export const IconoMayor = (p: Props) => (
  <Base {...p}>
    <rect x="3" y="4" width="8" height="7" rx="1" />
    <rect x="13" y="4" width="8" height="7" rx="1" />
    <rect x="3" y="13" width="18" height="7" rx="1" />
  </Base>
);

export const IconoBalanza = (p: Props) => (
  <Base {...p}>
    <path d="M12 4v16M7 20h10" />
    <path d="M5 8h14" />
    <path d="M5 8 2.5 14h5z" />
    <path d="M19 8l-2.5 6h5z" />
  </Base>
);

export const IconoResultados = (p: Props) => (
  <Base {...p}>
    <path d="M4 20V10M10 20V4M16 20v-7M22 20H2" />
  </Base>
);

export const IconoBalanceGeneral = (p: Props) => (
  <Base {...p}>
    <path d="M3 21h18" />
    <path d="M5 21V9l7-5 7 5v12" />
    <path d="M9.5 21v-6h5v6" />
  </Base>
);

export const IconoPdf = (p: Props) => (
  <Base {...p}>
    <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" />
    <path d="M14 3v5h5" />
    <path d="M9 14h6M9 17h4" />
  </Base>
);

export const IconoCasos = (p: Props) => (
  <Base {...p}>
    <path d="M3 7h6l2 2h10v10a2 2 0 0 1-2 2H3z" />
    <path d="M3 7V5h6l2 2" />
  </Base>
);

export const IconoAjustes = (p: Props) => (
  <Base {...p}>
    <circle cx="12" cy="12" r="3" />
    <path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-2.9 1.2V21a2 2 0 1 1-4 0v-.1A1.7 1.7 0 0 0 7 19.4a1.7 1.7 0 0 0-1.9.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1A1.7 1.7 0 0 0 3 15a1.7 1.7 0 0 0-1.5-1H1.4a2 2 0 1 1 0-4h.1A1.7 1.7 0 0 0 3 9a1.7 1.7 0 0 0-.3-1.9l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1A1.7 1.7 0 0 0 9 3.6V3.5a2 2 0 1 1 4 0v.1A1.7 1.7 0 0 0 15 5a1.7 1.7 0 0 0 1.9-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.9 1.7 1.7 0 0 0 1.5 1h.1a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z" />
  </Base>
);

export const IconoMas = (p: Props) => (
  <Base {...p}>
    <path d="M12 5v14M5 12h14" />
  </Base>
);

export const IconoLapiz = (p: Props) => (
  <Base {...p}>
    <path d="M12 20h9" />
    <path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z" />
  </Base>
);

export const IconoBasura = (p: Props) => (
  <Base {...p}>
    <path d="M3 6h18M8 6V4h8v2M6 6l1 14h10l1-14" />
    <path d="M10 11v6M14 11v6" />
  </Base>
);

export const IconoDescargar = (p: Props) => (
  <Base {...p}>
    <path d="M12 3v12" />
    <path d="m7 11 5 5 5-5" />
    <path d="M4 21h16" />
  </Base>
);

export const IconoSubir = (p: Props) => (
  <Base {...p}>
    <path d="M12 21V9" />
    <path d="m7 13 5-5 5 5" />
    <path d="M4 3h16" />
  </Base>
);

export const IconoImprimir = (p: Props) => (
  <Base {...p}>
    <path d="M6 9V3h12v6" />
    <path d="M6 18H4a2 2 0 0 1-2-2v-4a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v4a2 2 0 0 1-2 2h-2" />
    <path d="M6 14h12v7H6z" />
  </Base>
);

export const IconoCheck = (p: Props) => (
  <Base {...p}>
    <path d="m4 12.5 5 5L20 6.5" />
  </Base>
);

export const IconoAlerta = (p: Props) => (
  <Base {...p}>
    <path d="M12 3 1.8 20.5h20.4z" />
    <path d="M12 9v5M12 17.5h.01" />
  </Base>
);

export const IconoMenu = (p: Props) => (
  <Base {...p}>
    <path d="M4 7h16M4 12h16M4 17h16" />
  </Base>
);

export const IconoCerrar = (p: Props) => (
  <Base {...p}>
    <path d="M6 6l12 12M18 6 6 18" />
  </Base>
);

export const IconoCopiar = (p: Props) => (
  <Base {...p}>
    <rect x="9" y="9" width="12" height="12" rx="2" />
    <path d="M5 15V5a2 2 0 0 1 2-2h10" />
  </Base>
);

export const IconoCorreo = (p: Props) => (
  <Base {...p}>
    <rect x="2.5" y="5" width="19" height="14" rx="2" />
    <path d="m3 7 9 6 9-6" />
  </Base>
);
