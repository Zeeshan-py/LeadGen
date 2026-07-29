"use client";

import Script from "next/script";
import { usePathname } from "next/navigation";
import { useEffect, useRef } from "react";
import { useReportWebVitals } from "next/web-vitals";

import {
  GA_MEASUREMENT_ID,
  GTM_ID,
  analyticsEnabled,
  trackAppError,
  trackPageView,
  trackPerformanceMetric,
} from "@/lib/analytics";

function WebVitalsReporter() {
  useReportWebVitals((metric) => {
    trackPerformanceMetric(metric);
  });
  return null;
}

function PageViewReporter() {
  const pathname = usePathname();
  const lastTracked = useRef("");

  useEffect(() => {
    if (!analyticsEnabled()) return;
    const current = `${window.location.pathname}${window.location.search}`;
    if (lastTracked.current === current) return;
    lastTracked.current = current;
    trackPageView(window.location.href, document.title);
  }, [pathname]);

  return null;
}

function ErrorReporter() {
  useEffect(() => {
    const onError = (event: ErrorEvent) => {
      trackAppError(event.message || "Unhandled browser error", false);
    };
    const onRejection = (event: PromiseRejectionEvent) => {
      const reason = event.reason instanceof Error ? event.reason.message : String(event.reason);
      trackAppError(reason || "Unhandled promise rejection", false);
    };
    window.addEventListener("error", onError);
    window.addEventListener("unhandledrejection", onRejection);
    return () => {
      window.removeEventListener("error", onError);
      window.removeEventListener("unhandledrejection", onRejection);
    };
  }, []);

  return null;
}

export function AnalyticsProvider() {
  return (
    <>
      {analyticsEnabled() ? (
        <Script id="leadforge-consent-default" strategy="afterInteractive">
          {`
            window.dataLayer = window.dataLayer || [];
            function gtag(){dataLayer.push(arguments);}
            gtag('consent', 'default', {
              ad_storage: 'denied',
              ad_user_data: 'denied',
              ad_personalization: 'denied',
              analytics_storage: 'granted'
            });
          `}
        </Script>
      ) : null}

      {GTM_ID ? (
        <Script id="leadforge-gtm" strategy="afterInteractive">
          {`
            (function(w,d,s,l,i){w[l]=w[l]||[];w[l].push({'gtm.start':
            new Date().getTime(),event:'gtm.js'});var f=d.getElementsByTagName(s)[0],
            j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src=
            'https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f);
            })(window,document,'script','dataLayer','${GTM_ID}');
          `}
        </Script>
      ) : null}

      {GA_MEASUREMENT_ID ? (
        <>
          <Script
            id="leadforge-ga-src"
            src={`https://www.googletagmanager.com/gtag/js?id=${GA_MEASUREMENT_ID}`}
            strategy="afterInteractive"
          />
          <Script id="leadforge-ga-init" strategy="afterInteractive">
            {`
              window.dataLayer = window.dataLayer || [];
              function gtag(){dataLayer.push(arguments);}
              gtag('js', new Date());
              gtag('config', '${GA_MEASUREMENT_ID}', { send_page_view: false });
            `}
          </Script>
        </>
      ) : null}

      {GTM_ID ? (
        <noscript>
          <iframe
            src={`https://www.googletagmanager.com/ns.html?id=${GTM_ID}`}
            height="0"
            width="0"
            title="Google Tag Manager"
            className="hidden"
          />
        </noscript>
      ) : null}

      <PageViewReporter />
      <WebVitalsReporter />
      <ErrorReporter />
    </>
  );
}
