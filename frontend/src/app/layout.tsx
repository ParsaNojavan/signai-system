import "./globals.css";
import { AuthProvider } from "@/context/AuthContext";

export const metadata = {
  title: "SignAI - سامانه بلادرنگ زبان اشاره",
  description: "تشخیص هوشمند حرکات دست و زبان اشاره با یادگیری ماشین",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="fa" dir="rtl">
      <body className="bg-zinc-950 text-zinc-100 antialiased selection:bg-emerald-500/30 selection:text-emerald-300">
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
