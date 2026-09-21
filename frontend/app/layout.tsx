import type { Metadata } from "next";
import "./globals.css";
export const metadata: Metadata = {
  metadataBase: new URL("https://mama.neyrix-ai.ru"),
  title: "Neyrix Mama — AI-ассистент по беременности",
  description:
    "Персональный AI-ассистент для беременности: анализы, УЗИ, динамика показателей, питание, тренировки и сопровождение от первых недель до родов.",
  openGraph: {
    title: "Neyrix Mama",
    description: "Беременность. Понятно. Спокойно. Рядом.",
    images: ["/logo.png"],
  },
  icons: { icon: "/favicon.svg", apple: "/icon.png" },
};
export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ru">
      <body>{children}</body>
    </html>
  );
}
