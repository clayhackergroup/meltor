const fs = require('fs');
const path = require('path');
const acorn = require('acorn');
const walk = require('acorn-walk');

const API_PATTERNS = {
    PATH: /^\/(?:api|v[1-9]|graphql|rest|swagger|openapi)(?:\/|$)/i,
    COMMON_RESOURCE: /^\/(?:auth|login|register|logout|token|oauth|users?|posts?|comments?|todos?|items?|products?|orders?|payments?|webhooks?|notifications?|messages?|search|upload|files?|media|sockets?|events?|stream|health|status|config|settings?|preferences?|profiles?|avatars?|images?|docs?|help|export|import|sync|backup|restore|deploy|publish|draft|archive|trash|reviews?|ratings?|likes?|shares?|follows?|subscriptions?|invoices?|receipts?|transactions?|balances?|wallets?|organizations?|workspaces?|teams?|projects?|boards?|tickets?|issues?|milestones?|sprints?|tasks?|analytics?|reports?|dashboards?|metrics?|alerts?|callbacks?|hooks?|sso|saml|oidc|webauthn|mfa|2fa|servers?|nodes?|clusters?|regions?|zones?|subdomains?|domains?|dns|ssl|tls|certificates?|functions?|triggers?|schedules?|crons?|caches?|queues?|jobs?|workers?|addresses?|contacts?|leads?|deals?|opportunities?|documents?|attachments?|templates?|schemas?|versions?|releases?|changelogs?|roadmaps?|moderation|flags?|reports?|appeals?|sso|saml|oidc|webauthn|mfa|2fa|servers?|nodes?|clusters?|regions?|zones?|subdomains?|domains?|dns|ssl|tls|certificates?|functions?|triggers?|schedules?|crons?|caches?|queues?|jobs?|workers?)\b/i,
    FILE_EXT: /\.(json|php|aspx|ashx|jsp|do|action)$/i,
    FULL_URL: /^https?:\/\//i,
    PROTOCOL_REL: /^\/\//,
};

const SDK_API_PATTERNS = [
    // Firebase
    { regex: /firebase\.app\.[a-z]+\(['"]([^'"]+)['"]\)/, group: 1, label: 'firebase' },
    { regex: /firestore\(\)\.collection\(['"]([^'"]+)['"]\)/, group: 1, label: 'firestore' },
    { regex: /database\(\)\.ref\(['"]([^'"]+)['"]\)/, group: 1, label: 'firebase-db' },
    { regex: /firebase\.initializeApp\(\{[^}]*apiKey[^}]*\}\)/, group: 0, label: 'firebase-config' },
    // AWS
    { regex: /new\s+AWS\.\w+\(\{[^}]*endpoint:\s*['"]([^'"]+)['"]/, group: 1, label: 'aws-sdk' },
    { regex: /AWS\.config\.update\(\{[^}]*endpoint:\s*['"]([^'"]+)['"]/, group: 1, label: 'aws-config' },
    { regex: /S3\(\{[^}]*endpoint:\s*['"]([^'"]+)['"]/, group: 1, label: 'aws-s3' },
    { regex: /new\s+DynamoDB\.DocumentClient/, group: 0, label: 'aws-dynamodb' },
    { regex: /API Gateway\.\w+\(['"]([^'"]+)['"]\)/, group: 1, label: 'aws-apigw' },
    { regex: /new\s+ApiGateway\(\{[^}]*endpoint:\s*['"]([^'"]+)['"]/, group: 1, label: 'aws-apigw' },
    { regex: /lambda\.invoke\(\{[^}]*FunctionName:\s*['"]([^'"]+)['"]/, group: 1, label: 'aws-lambda' },
    // Stripe
    { regex: /stripe\(['"]([^'"]+)['"]\)/, group: 1, label: 'stripe' },
    { regex: /new\s+Stripe\(['"]([^'"]+)['"]/, group: 1, label: 'stripe' },
    { regex: /stripe\.\w+\.\w+\(['"]([^'"]+)['"]/, group: 1, label: 'stripe-api' },
    { regex: /stripe\(\)\.\w+\.\w+\(['"]([^'"]+)['"]/, group: 1, label: 'stripe-api' },
    // PayPal
    { regex: /paypal\.Buttons\.render/, group: 0, label: 'paypal' },
    { regex: /paypal\.Checkout\.\w+\(['"]([^'"]+)['"]/, group: 1, label: 'paypal-api' },
    { regex: /paypal\.Rest\.\w+\(['"]([^'"]+)['"]/, group: 1, label: 'paypal-api' },
    // Google Maps
    { regex: /google\.maps\.\w+\(\{[^}]*url:\s*['"]([^'"]+)['"]/, group: 1, label: 'google-maps' },
    { regex: /new\s+google\.maps\.\w+\(\{[^}]*url:\s*['"]([^'"]+)['"]/, group: 1, label: 'google-maps' },
    { regex: /Geocoder\(\)\.geocode\(\{[^}]*address:\s*['"]([^'"]+)['"]/, group: 1, label: 'google-geocoder' },
    { regex: /PlacesService\(\)\.\w+\(\{[^}]*query:\s*['"]([^'"]+)['"]/, group: 1, label: 'google-places' },
    // reCAPTCHA
    { regex: /grecaptcha\.\w+\(['"]([^'"]+)['"]/, group: 1, label: 'recaptcha' },
    { regex: /grecaptcha\.render\(['"]([^'"]+)['"]/, group: 1, label: 'recaptcha' },
    { regex: /class\s+Recaptcha/, group: 0, label: 'recaptcha' },
    // Cloudinary
    { regex: /cloudinary\.\w+\(\{[^}]*url:\s*['"]([^'"]+)['"]/, group: 1, label: 'cloudinary' },
    { regex: /cloudinary\.uploader\.\w+\(['"]([^'"]+)['"]/, group: 1, label: 'cloudinary' },
    // Algolia
    { regex: /algoliasearch\(['"]([^'"]+)['"]/, group: 1, label: 'algolia' },
    { regex: /new\s+AlgoliaSearch\(['"]([^'"]+)['"]/, group: 1, label: 'algolia' },
    { regex: /searchClient\.\w+\(['"]([^'"]+)['"]/, group: 1, label: 'algolia' },
    // Auth0
    { regex: /new\s+Auth0Client\(\{[^}]*domain:\s*['"]([^'"]+)['"]/, group: 1, label: 'auth0' },
    { regex: /auth0\.\w+\(['"]([^'"]+)['"]/, group: 1, label: 'auth0' },
    { regex: /createAuth0Client\(\{[^}]*domain:\s*['"]([^'"]+)['"]/, group: 1, label: 'auth0' },
    // Okta
    { regex: /new\s+OktaAuth\(\{[^}]*issuer:\s*['"]([^'"]+)['"]/, group: 1, label: 'okta' },
    { regex: /oktaSignIn\.\w+\(['"]([^'"]+)['"]/, group: 1, label: 'okta' },
    // Supabase
    { regex: /createClient\(['"]([^'"]+)['"]/, group: 1, label: 'supabase' },
    { regex: /supabase\.\w+\.\w+\(['"]([^'"]+)['"]/, group: 1, label: 'supabase' },
    { regex: /supabaseClient\.\w+\(['"]([^'"]+)['"]/, group: 1, label: 'supabase' },
    { regex: /from\(['"]([^'"]+)['"]\)\.\w+/, group: 1, label: 'supabase-table' },
    // Contentful
    { regex: /createClient\(\{[^}]*space:\s*['"]([^'"]+)['"]/, group: 1, label: 'contentful' },
    { regex: /contentful\.\w+\(['"]([^'"]+)['"]/, group: 1, label: 'contentful' },
    // Sanity
    { regex: /sanityClient\.\w+\(['"]([^'"]+)['"]/, group: 1, label: 'sanity' },
    { regex: /client\.fetch\(['"]([^'"]+)['"]/, group: 1, label: 'sanity-groq' },
    { regex: /@sanity\/client/, group: 0, label: 'sanity' },
    // GraphQL (generic)
    { regex: /graphql\(['"]([^'"]+)['"]/, group: 1, label: 'graphql' },
    { regex: /gql`([^`]+)`/, group: 1, label: 'gql-template' },
    { regex: /request\(['"]([^'"]+)['"]/, group: 1, label: 'graphql-request' },
    // Apollo
    { regex: /ApolloClient\(\{[^}]*uri:\s*['"]([^'"]+)['"]/, group: 1, label: 'apollo' },
    { regex: /new\s+ApolloClient\(\{[^}]*uri:\s*['"]([^'"]+)['"]/, group: 1, label: 'apollo' },
    { regex: /client\.query\(\{[^}]*query:\s*gql`/, group: 1, label: 'apollo-query' },
    { regex: /client\.mutate\(\{[^}]*mutation:\s*gql`/, group: 1, label: 'apollo-mutation' },
    { regex: /useQuery\(gql`([^`]+)`/, group: 1, label: 'apollo-usequery' },
    { regex: /useMutation\(gql`([^`]+)`/, group: 1, label: 'apollo-usemutation' },
    // Relay
    { regex: /commitMutation\(\{[^}]*mutation:\s*gql`/, group: 1, label: 'relay' },
    { regex: /fetchQuery\(\{[^}]*query:\s*gql`/, group: 1, label: 'relay-query' },
    { regex: /graphql`([^`]+)`/, group: 1, label: 'relay-gql' },
    // SWR
    { regex: /useSWR\(['"]([^'"]+)['"]/, group: 1, label: 'swr' },
    { regex: /useSWR\(`([^`]+)`/, group: 1, label: 'swr-template' },
    // React Query / TanStack Query
    { regex: /useQuery\(\{[^}]*queryKey:\s*\[['"]([^'"]+)['"]/, group: 1, label: 'react-query' },
    { regex: /useQuery\(['"]([^'"]+)['"]/, group: 1, label: 'react-query' },
    { regex: /queryClient\.fetchQuery\(['"]([^'"]+)['"]/, group: 1, label: 'react-query' },
    { regex: /useMutation\(\{[^}]*mutationKey:\s*\[['"]([^'"]+)['"]/, group: 1, label: 'react-query-mut' },
    // tRPC
    { regex: /createTRPCClient\(\{[^}]*url:\s*['"]([^'"]+)['"]/, group: 1, label: 'trpc' },
    { regex: /trpc\.\w+\.\w+\.query\(['"]([^'"]+)['"]/, group: 1, label: 'trpc-query' },
    { regex: /trpc\.\w+\.\w+\.mutate\(['"]([^'"]+)['"]/, group: 1, label: 'trpc-mutate' },
    { regex: /trpcClient\.\w+\.\w+\.query\(/, group: 0, label: 'trpc' },
    { regex: /httpBatchLink\(\{[^}]*url:\s*['"]([^'"]+)['"]/, group: 1, label: 'trpc-link' },
    // Socket.io
    { regex: /io\(['"]([^'"]+)['"]/, group: 1, label: 'socketio' },
    { regex: /io\(`([^`]+)`/, group: 1, label: 'socketio-template' },
    { regex: /socket\.emit\(['"]([^'"]+)['"]/, group: 1, label: 'socketio-event' },
    { regex: /socket\.on\(['"]([^'"]+)['"]/, group: 1, label: 'socketio-event' },
    // Pusher
    { regex: /new\s+Pusher\(['"]([^'"]+)['"]/, group: 1, label: 'pusher' },
    { regex: /pusher\.\w+\(['"]([^'"]+)['"]/, group: 1, label: 'pusher' },
    // Ably
    { regex: /new\s+Ably\.Realtime\(['"]([^'"]+)['"]/, group: 1, label: 'ably' },
    { regex: /ably\.\w+\.\w+\(['"]([^'"]+)['"]/, group: 1, label: 'ably' },
    // Sentry
    { regex: /Sentry\.init\(\{[^}]*dsn:\s*['"]([^'"]+)['"]/, group: 1, label: 'sentry' },
    { regex: /new\s+Sentry\.\w+\(['"]([^'"]+)['"]/, group: 1, label: 'sentry' },
    // Datadog
    { regex: /datadogRum\.init\(\{[^}]*applicationId:\s*['"]([^'"]+)['"]/, group: 1, label: 'datadog-rum' },
    { regex: /datadogLogs\.init\(\{[^}]*clientToken:\s*['"]([^'"]+)['"]/, group: 1, label: 'datadog-logs' },
    // Mixpanel
    { regex: /mixpanel\.init\(['"]([^'"]+)['"]/, group: 1, label: 'mixpanel' },
    { regex: /mixpanel\.track\(['"]([^'"]+)['"]/, group: 1, label: 'mixpanel-event' },
    // Segment
    { regex: /analytics\.load\(['"]([^'"]+)['"]/, group: 1, label: 'segment' },
    { regex: /analytics\.track\(['"]([^'"]+)['"]/, group: 1, label: 'segment-event' },
    // Amplitude
    { regex: /amplitude\.init\(['"]([^'"]+)['"]/, group: 1, label: 'amplitude' },
    { regex: /amplitude\.track\(['"]([^'"]+)['"]/, group: 1, label: 'amplitude-event' },
    // Hotjar
    { regex: /hotjar\.\w+\(['"]([^'"]+)['"]/, group: 1, label: 'hotjar' },
    { regex: /hj\(['"]([^'"]+)['"]/, group: 1, label: 'hotjar' },
    // HubSpot
    { regex: /HubSpotForm\.\w+\(['"]([^'"]+)['"]/, group: 1, label: 'hubspot' },
    // Intercom
    { regex: /Intercom\(['"]([^'"]+)['"]/, group: 1, label: 'intercom' },
    { regex: /window\.Intercom\(['"]([^'"]+)['"]/, group: 1, label: 'intercom' },
    // Zendesk
    { regex: /zE\(['"]([^'"]+)['"]/, group: 1, label: 'zendesk' },
    // Salesforce
    { regex: /force\.\w+\(['"]([^'"]+)['"]/, group: 1, label: 'salesforce' },
    { regex: /Visualforce\.\w+\(['"]([^'"]+)['"]/, group: 1, label: 'salesforce' },
    // Auth.js / NextAuth
    { regex: /signIn\(['"]([^'"]+)['"]/, group: 1, label: 'nextauth' },
    { regex: /getSession\(\)/, group: 0, label: 'nextauth' },
    // Next.js
    { regex: /getServerSideProps/, group: 0, label: 'nextjs-ssr' },
    { regex: /getStaticProps/, group: 0, label: 'nextjs-ssg' },
    { regex: /getStaticPaths/, group: 0, label: 'nextjs-ssg' },
    { regex: /next\/router/, group: 0, label: 'nextjs' },
    // Remix
    { regex: /loader\(\{[^}]*request/, group: 0, label: 'remix-loader' },
    { regex: /action\(\{[^}]*request/, group: 0, label: 'remix-action' },
    // Nuxt
    { regex: /useFetch\(['"]([^'"]+)['"]/, group: 1, label: 'nuxt-fetch' },
    { regex: /useLazyFetch\(['"]([^'"]+)['"]/, group: 1, label: 'nuxt-fetch' },
    // SvelteKit
    { regex: /load\(\{[^}]*fetch/, group: 0, label: 'sveltekit-load' },
    { regex: /actions:\s*\{/, group: 0, label: 'sveltekit-actions' },
    // WebSocket
    { regex: /new\s+WebSocket\(['"]([^'"]+)['"]/, group: 1, label: 'websocket' },
    { regex: /new\s+WebSocket\(`([^`]+)`/, group: 1, label: 'websocket-template' },
    // EventSource / SSE
    { regex: /new\s+EventSource\(['"]([^'"]+)['"]/, group: 1, label: 'eventsource' },
    { regex: /new\s+EventSource\(`([^`]+)`/, group: 1, label: 'eventsource-template' },
    // Service Worker
    { regex: /navigator\.serviceWorker\.register\(['"]([^'"]+)['"]/, group: 1, label: 'sw-register' },
    { regex: /self\.addEventListener\('fetch'/, group: 0, label: 'sw-fetch' },
    // JSON-RPC
    { regex: /jsonrpc.*['"]method['"]\s*:\s*['"]([^'"]+)['"]/, group: 1, label: 'jsonrpc' },
    // Web Push
    { regex: /Notification\.requestPermission/, group: 0, label: 'web-push' },
    { regex: /pushManager\.\w+\(/, group: 0, label: 'web-push' },
    // Stripe Checkout
    { regex: /stripe\.redirectToCheckout\(\{[^}]*sessionId:\s*['"]([^'"]+)['"]/, group: 1, label: 'stripe-checkout' },
    // Firebase Cloud Messaging
    { regex: /messaging\(\)\.\w+\(['"]([^'"]+)['"]/, group: 1, label: 'fcm' },
    // Firebase Cloud Functions
    { regex: /functions\(\)\.\w+\(['"]([^'"]+)['"]/, group: 1, label: 'firebase-fn' },
    // AWS Amplify
    { regex: /Amplify\.configure\(\{[^}]*endpoint:\s*['"]([^'"]+)['"]/, group: 1, label: 'amplify' },
    { regex: /API\.\w+\(['"]([^'"]+)['"]/, group: 1, label: 'amplify-api' },
    // Twilio
    { regex: /Twilio\.\w+\(['"]([^'"]+)['"]/, group: 1, label: 'twilio' },
    // SendGrid
    { regex: /sendgrid\.\w+\(['"]([^'"]+)['"]/, group: 1, label: 'sendgrid' },
    // Mailgun
    { regex: /mailgun\(\)\.\w+\(['"]([^'"]+)['"]/, group: 1, label: 'mailgun' },
    // Mailchimp
    { regex: /mailchimp\.\w+\(['"]([^'"]+)['"]/, group: 1, label: 'mailchimp' },
    // Shopify
    { regex: /Shopify\.\w+\.\w+\(['"]([^'"]+)['"]/, group: 1, label: 'shopify' },
    // Appwrite
    { regex: /appwrite\.\w+\.\w+\(['"]([^'"]+)['"]/, group: 1, label: 'appwrite' },
    { regex: /new\s+Appwrite/, group: 0, label: 'appwrite' },
    // Hasura
    { regex: /hasuraClient\.\w+\(['"]([^'"]+)['"]/, group: 1, label: 'hasura' },
    // Strapi
    { regex: /strapi\.\w+\(['"]([^'"]+)['"]/, group: 1, label: 'strapi' },
    // gRPC-web
    { regex: /GrpcWebClient\(\{[^}]*url:\s*['"]([^'"]+)['"]/, group: 1, label: 'grpc-web' },
    { regex: /grpc\.\w+\(['"]([^'"]+)['"]/, group: 1, label: 'grpc' },
    // tRPC React
    { regex: /trpcReact\.\w+\.\w+\.useQuery\(/, group: 0, label: 'trpc-react' },
    // Vue Query
    { regex: /useQuery\(['"]([^'"]+)['"]/, group: 1, label: 'vue-query' },
    // RTK Query
    { regex: /createApi\(\{[^}]*baseUrl:\s*['"]([^'"]+)['"]/, group: 1, label: 'rtk-query' },
    { regex: /createApi\(\{[^}]*baseQuery:\s*fetchBaseQuery\(\{[^}]*baseUrl:\s*['"]([^'"]+)['"]/, group: 1, label: 'rtk-query' },
    // Apollo Client (alternative syntax)
    { regex: /useApolloClient\(\)/, group: 0, label: 'apollo' },
    // urql
    { regex: /createClient\(\{[^}]*url:\s*['"]([^'"]+)['"]/, group: 1, label: 'urql' },
    // React Relay
    { regex: /RelayEnvironment\.\w+\(['"]([^'"]+)['"]/, group: 1, label: 'relay-env' },
    // RxJS WebSocket
    { regex: /webSocket\(['"]([^'"]+)['"]/, group: 1, label: 'rxjs-ws' },
    // MQTT
    { regex: /mqtt\.connect\(['"]([^'"]+)['"]/, group: 1, label: 'mqtt' },
    // STOMP
    { regex: /Stomp\.client\(['"]([^'"]+)['"]/, group: 1, label: 'stomp' },
    // Payment Request API
    { regex: /PaymentRequest\(\[[^\]]*\],\s*\{[^}]*total:/, group: 0, label: 'payment-request' },
    // Google Tag Manager
    { regex: /googletag\.\w+\(['"]([^'"]+)['"]/, group: 1, label: 'gtag' },
    // Google Analytics
    { regex: /gtag\(['"]([^'"]+)['"]/, group: 1, label: 'ga' },
    { regex: /ga\(['"]([^'"]+)['"]/, group: 1, label: 'ga' },
    // Facebook Pixel
    { regex: /fbq\(['"]([^'"]+)['"]/, group: 1, label: 'fb-pixel' },
    // LinkedIn Insight
    { regex: /_linkedin_partner_id/, group: 0, label: 'linkedin-insight' },
    // Twitter Pixel
    { regex: /twq\(['"]([^'"]+)['"]/, group: 1, label: 'twitter-pixel' },
    // Pinterest Tag
    { regex: /pintrk\(['"]([^'"]+)['"]/, group: 1, label: 'pinterest-tag' },
    // Reddit Pixel
    { regex: /rdt\(['"]([^'"]+)['"]/, group: 1, label: 'reddit-pixel' },
    // TikTok Pixel
    { regex: /ttq\.\w+\(['"]([^'"]+)['"]/, group: 1, label: 'tiktok-pixel' },
    // Snapchat Pixel
    { regex: /snaptr\.\w+\(['"]([^'"]+)['"]/, group: 1, label: 'snapchat-pixel' },
    // Microsoft Clarity
    { regex: /clarity\.\w+\(['"]([^'"]+)['"]/, group: 1, label: 'clarity' },
    // FullStory
    { regex: /FS\.\w+\(['"]([^'"]+)['"]/, group: 1, label: 'fullstory' },
    // LogRocket
    { regex: /LogRocket\.init\(['"]([^'"]+)['"]/, group: 1, label: 'logrocket' },
    // PostHog
    { regex: /posthog\.init\(['"]([^'"]+)['"]/, group: 1, label: 'posthog' },
    { regex: /posthog\.capture\(['"]([^'"]+)['"]/, group: 1, label: 'posthog-event' },
    // Heap
    { regex: /heap\.\w+\(['"]([^'"]+)['"]/, group: 1, label: 'heap' },
    // Smartlook
    { regex: /smartlook\.\w+\(['"]([^'"]+)['"]/, group: 1, label: 'smartlook' },
    // Auth0 SPA
    { regex: /Auth0Client\.\w+\(['"]([^'"]+)['"]/, group: 1, label: 'auth0-spa' },
    // Clerk
    { regex: /Clerk\.\w+\(['"]([^'"]+)['"]/, group: 1, label: 'clerk' },
    { regex: /clerkClient\.\w+\(['"]([^'"]+)['"]/, group: 1, label: 'clerk' },
    // Kinde
    { regex: /Kinde\.\w+\(['"]([^'"]+)['"]/, group: 1, label: 'kinde' },
    // WorkOS
    { regex: /WorkOS\.\w+\(['"]([^'"]+)['"]/, group: 1, label: 'workos' },
    // Clerk NextJS
    { regex: /auth\(\)\.\w+\(['"]([^'"]+)['"]/, group: 1, label: 'clerk-auth' },
    // UploadThing
    { regex: /uploadthing\.\w+\(['"]([^'"]+)['"]/, group: 1, label: 'uploadthing' },
    // Liveblocks
    { regex: /liveblocks\.\w+\(['"]([^'"]+)['"]/, group: 1, label: 'liveblocks' },
    // PartyKit
    { regex: /partykit\.\w+\(['"]([^'"]+)['"]/, group: 1, label: 'partykit' },
    // Replicate
    { regex: /Replicate\.\w+\(['"]([^'"]+)['"]/, group: 1, label: 'replicate' },
    // OpenAI
    { regex: /openai\.\w+\(['"]([^'"]+)['"]/, group: 1, label: 'openai' },
    { regex: /OpenAI\.\w+\(['"]([^'"]+)['"]/, group: 1, label: 'openai' },
    // Anthropic
    { regex: /anthropic\.\w+\(['"]([^'"]+)['"]/, group: 1, label: 'anthropic' },
    // Hugging Face
    { regex: /huggingface\.\w+\(['"]([^'"]+)['"]/, group: 1, label: 'huggingface' },
    // Pinata (IPFS)
    { regex: /pinata\.\w+\(['"]([^'"]+)['"]/, group: 1, label: 'pinata' },
    // Web3 / Ethereum
    { regex: /new\s+Web3\(['"]([^'"]+)['"]/, group: 1, label: 'web3' },
    { regex: /ethers\.\w+\.\w+\(['"]([^'"]+)['"]/, group: 1, label: 'ethers' },
    { regex: /new\s+ethers\.\w+\(['"]([^'"]+)['"]/, group: 1, label: 'ethers' },
    // Alchemy
    { regex: /alchemy\.\w+\(['"]([^'"]+)['"]/, group: 1, label: 'alchemy' },
    // Moralis
    { regex: /Moralis\.\w+\(['"]([^'"]+)['"]/, group: 1, label: 'moralis' },
    // Thirdweb
    { regex: /thirdweb\.\w+\(['"]([^'"]+)['"]/, group: 1, label: 'thirdweb' },
    // Sanity Client (alternative)
    { regex: /@sanity\/client/, group: 0, label: 'sanity-client' },
    // Datocms
    { regex: /datocms\.\w+\(['"]([^'"]+)['"]/, group: 1, label: 'datocms' },
    // Prismic
    { regex: /prismic\.\w+\(['"]([^'"]+)['"]/, group: 1, label: 'prismic' },
    // Ghost CMS
    { regex: /ghost\.\w+\(['"]([^'"]+)['"]/, group: 1, label: 'ghost' },
    // Builder.io
    { regex: /builder\.\w+\(['"]([^'"]+)['"]/, group: 1, label: 'builderio' },
    // Webflow
    { regex: /webflow\.\w+\(['"]([^'"]+)['"]/, group: 1, label: 'webflow' },
    // Storyblok
    { regex: /storyblok\.\w+\(['"]([^'"]+)['"]/, group: 1, label: 'storyblok' },
    // Hygraph
    { regex: /hygraph\.\w+\(['"]([^'"]+)['"]/, group: 1, label: 'hygraph' },
    // GraphCMS
    { regex: /graphcms\.\w+\(['"]([^'"]+)['"]/, group: 1, label: 'graphcms' },
    // Cockpit CMS
    { regex: /cockpit\.\w+\(['"]([^'"]+)['"]/, group: 1, label: 'cockpit' },
    // Directus
    { regex: /directus\.\w+\(['"]([^'"]+)['"]/, group: 1, label: 'directus' },
    // Payload CMS
    { regex: /payload\.\w+\(['"]([^'"]+)['"]/, group: 1, label: 'payload' },
    // Keystone
    { regex: /keystone\.\w+\(['"]([^'"]+)['"]/, group: 1, label: 'keystone' },
];

const COMMON_METHODS = ['get', 'post', 'put', 'delete', 'patch', 'head', 'options'];

function isApiUrl(str) {
    if (!str || str.length < 3) return false;
    if (API_PATTERNS.FULL_URL.test(str)) {
        const pathname = str.replace(/^https?:\/\/[^\/]+/i, '');
        return isApiUrl(pathname);
    }
    if (API_PATTERNS.PROTOCOL_REL.test(str)) {
        const pathname = str.replace(/^\/\//, '/');
        return isApiUrl(pathname);
    }
    if (str.startsWith('/')) {
        if (API_PATTERNS.PATH.test(str)) return true;
        if (API_PATTERNS.COMMON_RESOURCE.test(str)) return true;
        if (API_PATTERNS.FILE_EXT.test(str)) return true;
    }
    if (API_PATTERNS.PATH.test('/' + str) || API_PATTERNS.COMMON_RESOURCE.test('/' + str)) {
        return true;
    }
    // WebSocket protocol
    if (/^wss?:\/\//i.test(str)) return true;
    // Check for UUIDs in path
    if (/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i.test(str)) return true;
    // Check for API-like patterns
    if (/\/api\//i.test(str) || /\/v\d+\//i.test(str)) return true;
    if (/graphql/i.test(str)) return true;
    return false;
}

function normalizeUrl(url) {
    if (API_PATTERNS.FULL_URL.test(url) || API_PATTERNS.PROTOCOL_REL.test(url)) {
        return url;
    }
    if (/^wss?:\/\//i.test(url)) return url;
    if (url.startsWith('/')) {
        return url;
    }
    return '/' + url;
}

function extractNodeValue(node) {
    if (!node) return null;
    if (node.type === 'Literal' && typeof node.value === 'string') {
        return node.value;
    }
    if (node.type === 'Literal' && typeof node.value === 'number') {
        return String(node.value);
    }
    if (node.type === 'TemplateLiteral') {
        let result = '';
        for (let i = 0; i < node.quasis.length; i++) {
            result += node.quasis[i].value.raw;
            if (i < node.expressions.length) {
                const expr = node.expressions[i];
                if (expr.type === 'Identifier') {
                    result += `:${expr.name}`;
                } else if (expr.type === 'MemberExpression') {
                    result += ':param';
                } else if (expr.type === 'CallExpression') {
                    result += ':fn()';
                } else {
                    result += ':param';
                }
            }
        }
        return result;
    }
    if (node.type === 'BinaryExpression' && node.operator === '+') {
        const left = extractNodeValue(node.left);
        const right = extractNodeValue(node.right);
        if (left && right) return left + right;
        if (left) return left;
        if (right) return right;
    }
    if (node.type === 'Identifier') {
        return null;
    }
    if (node.type === 'MemberExpression' && !node.computed) {
        const obj = extractNodeValue(node.object);
        if (obj && node.property.type === 'Identifier') {
            return obj + '.' + node.property.name;
        }
        return null;
    }
    if (node.type === 'MemberExpression' && node.computed) {
        const obj = extractNodeValue(node.object);
        const prop = extractNodeValue(node.property);
        if (obj && prop) return obj + '[' + prop + ']';
        return null;
    }
    if (node.type === 'ConditionalExpression') {
        const cons = extractNodeValue(node.consequent);
        const alt = extractNodeValue(node.alternate);
        return cons || alt;
    }
    if (node.type === 'LogicalExpression') {
        const left = extractNodeValue(node.left);
        const right = extractNodeValue(node.right);
        return left || right;
    }
    if (node.type === 'ArrayExpression') {
        return null;
    }
    if (node.type === 'ObjectExpression') {
        return null;
    }
    if (node.type === 'UnaryExpression' && node.operator === '!') {
        return null;
    }
    return null;
}

function getCalleeChain(node) {
    if (node.type === 'Identifier') {
        return { chain: [node.name], obj: null };
    }
    if (node.type === 'MemberExpression' && !node.computed) {
        const left = getCalleeChain(node.object);
        const prop = node.property.type === 'Identifier' ? node.property.name : null;
        if (prop) {
            left.chain.push(prop);
        }
        return left;
    }
    if (node.type === 'MemberExpression' && node.computed) {
        const left = getCalleeChain(node.object);
        const prop = extractNodeValue(node.property);
        if (prop) {
            left.chain.push(prop);
        }
        return left;
    }
    if (node.type === 'CallExpression') {
        const callee = getCalleeChain(node.callee);
        callee.chain.push('()');
        return callee;
    }
    return { chain: [], obj: null };
}

function getUrlFromObject(objNode) {
    if (!objNode || objNode.type !== 'ObjectExpression') return null;
    for (const prop of objNode.properties) {
        const key = prop.key.type === 'Identifier' ? prop.key.name :
                    prop.key.type === 'Literal' ? prop.key.value : null;
        if (key && ['url', 'endpoint', 'uri', 'target', 'path'].includes(key.toLowerCase())) {
            const val = extractNodeValue(prop.value);
            if (val && isApiUrl(val)) return val;
        }
        if (key && ['baseurl', 'base_url', 'baseUrl', 'apiUrl', 'api_url', 'basePath', 'base_path'].includes(key)) {
            const val = extractNodeValue(prop.value);
            if (val) return val;
        }
    }
    return null;
}

function getStringFromObject(objNode, keyNames) {
    if (!objNode || objNode.type !== 'ObjectExpression') return null;
    keyNames = Array.isArray(keyNames) ? keyNames : [keyNames];
    for (const prop of objNode.properties) {
        const key = prop.key.type === 'Identifier' ? prop.key.name :
                    prop.key.type === 'Literal' ? prop.key.value : null;
        if (key && keyNames.includes(key)) {
            return extractNodeValue(prop.value);
        }
    }
    return null;
}

function extractMethodFromOptions(args) {
    if (!args || args.length < 2) return 'GET';
    const opts = args[1];
    if (opts && opts.type === 'ObjectExpression') {
        for (const prop of opts.properties) {
            const key = prop.key.type === 'Identifier' ? prop.key.name :
                        prop.key.type === 'Literal' ? prop.key.value : null;
            if (key && key.toLowerCase() === 'method') {
                const method = extractNodeValue(prop.value);
                if (method) return method.toUpperCase();
            }
        }
    }
    return 'GET';
}

function extractGraphQLOperations(code) {
    const endpoints = [];
    // Extract operation names from gql template literals and graphql strings
    const gqlPattern = /(?:gql|graphql)\s*(?:`([^`]+)`|\(['"]([^'"]+)['"]\))/g;
    let match;
    while ((match = gqlPattern.exec(code)) !== null) {
        const content = match[1] || match[2];
        if (content) {
            const queries = content.match(/(?:query|mutation|subscription)\s+(\w+)/gi);
            if (queries) {
                for (const q of queries) {
                    const parts = q.split(/\s+/);
                    if (parts.length >= 2) {
                        endpoints.push({
                            url: parts[1].toLowerCase(),
                            method: parts[0].toUpperCase() === 'MUTATION' ? 'POST' : 'GET',
                            confidence: 'medium',
                            type: 'graphql-operation'
                        });
                    }
                }
            }
        }
    }
    return endpoints;
}

function extractSDKPatterns(code, sourceFile) {
    const endpoints = [];
    for (const pattern of SDK_API_PATTERNS) {
        const regex = new RegExp(pattern.regex.source, pattern.regex.flags + 'g');
        let match;
        while ((match = regex.exec(code)) !== null) {
            const matched = match[pattern.group] || match[0];
            if (matched && matched.length > 2 && matched.length < 500) {
                const url = matched.trim();
                if (isApiUrl(url) || /^[a-zA-Z]/.test(url)) {
                    endpoints.push({
                        url: normalizeUrl(url),
                        method: 'GET',
                        confidence: 'high',
                        source: sourceFile || 'unknown',
                        info: `sdk:${pattern.label}`
                    });
                }
            }
        }
    }
    return endpoints;
}

function extractFromCall(node, calleeChain) {
    const chain = calleeChain.chain;
    const name = chain.join('.');

    const endpoints = [];

    // Direct fetch(url) or fetch(url, options)
    if (name === 'fetch' && node.arguments.length >= 1) {
        const url = extractNodeValue(node.arguments[0]);
        if (url && isApiUrl(url)) {
            const method = extractMethodFromOptions(node.arguments);
            endpoints.push({ url: normalizeUrl(url), method, confidence: 'high' });
            return endpoints;
        }
    }

    // fetch with Request object
    if (name === 'fetch' && node.arguments.length >= 1) {
        const first = node.arguments[0];
        if (first.type === 'NewExpression' && first.callee.name === 'Request') {
            if (first.arguments.length >= 1) {
                const url = extractNodeValue(first.arguments[0]);
                if (url && isApiUrl(url)) {
                    let method = 'GET';
                    if (first.arguments.length >= 2 && first.arguments[1].type === 'ObjectExpression') {
                        method = getStringFromObject(first.arguments[1], 'method') || 'GET';
                    }
                    endpoints.push({ url: normalizeUrl(url), method: method.toUpperCase(), confidence: 'high' });
                    return endpoints;
                }
            }
        }
    }

    // axios(url) or axios({url: ...})
    if (name === 'axios') {
        if (node.arguments.length >= 1) {
            const first = node.arguments[0];
            if (first.type === 'ObjectExpression') {
                const url = getUrlFromObject(first);
                if (url) {
                    const method = extractMethodFromOptions(node.arguments);
                    endpoints.push({ url: normalizeUrl(url), method, confidence: 'high' });
                }
            } else {
                const url = extractNodeValue(first);
                if (url && isApiUrl(url)) {
                    endpoints.push({ url: normalizeUrl(url), method: 'GET', confidence: 'high' });
                }
            }
        }
        return endpoints;
    }

    // axios.get/post/put/delete/patch(url)
    const methodCalleeMatch = name.match(/^(?:axios|\$|jQuery|app|router|server|api|client|httpClient|apiClient)\.(get|post|put|delete|patch|head|options)$/i);
    if (methodCalleeMatch && node.arguments.length >= 1) {
        const httpMethod = methodCalleeMatch[1].toUpperCase();
        const url = extractNodeValue(node.arguments[0]);
        if (url && isApiUrl(url)) {
            endpoints.push({ url: normalizeUrl(url), method: httpMethod, confidence: 'high' });
            return endpoints;
        }
    }

    // this.http.get/post(url), http.get/post(url)
    const httpMatch = name.match(/^(?:this\.)?http\.(get|post|put|delete|patch|head|options)$/i);
    if (httpMatch && node.arguments.length >= 1) {
        const httpMethod = httpMatch[1].toUpperCase();
        const url = extractNodeValue(node.arguments[0]);
        if (url && isApiUrl(url)) {
            endpoints.push({ url: normalizeUrl(url), method: httpMethod, confidence: 'high' });
            return endpoints;
        }
    }

    // $.ajax({url}), jQuery.ajax({url})
    if (name === '$.ajax' || name === 'jQuery.ajax') {
        if (node.arguments.length >= 1 && node.arguments[0].type === 'ObjectExpression') {
            const url = getUrlFromObject(node.arguments[0]);
            if (url) {
                const method = extractMethodFromOptions(node.arguments);
                endpoints.push({ url: normalizeUrl(url), method, confidence: 'high' });
            }
        }
        return endpoints;
    }

    // $.getJSON(url)
    if (name === '$.getJSON' && node.arguments.length >= 1) {
        const url = extractNodeValue(node.arguments[0]);
        if (url && isApiUrl(url)) {
            endpoints.push({ url: normalizeUrl(url), method: 'GET', confidence: 'high' });
        }
        return endpoints;
    }

    // axios.create({baseURL: ...}) -> extract base URL
    if (name === 'axios.create' && node.arguments.length >= 1) {
        const first = node.arguments[0];
        if (first.type === 'ObjectExpression') {
            for (const prop of first.properties) {
                const key = prop.key.type === 'Identifier' ? prop.key.name :
                            prop.key.type === 'Literal' ? prop.key.value : null;
                if (key && ['baseurl', 'base_url', 'baseUrl', 'baseURL'].includes(key)) {
                    const val = extractNodeValue(prop.value);
                    if (val) {
                        endpoints.push({ url: normalizeUrl(val), method: 'GET', confidence: 'medium', info: 'base_url' });
                    }
                }
            }
        }
        return endpoints;
    }

    // app.use('/api', router) -> extract mount path
    if ((name === 'app.use' || name === 'server.use' || name === 'router.use') && node.arguments.length >= 1) {
        const url = extractNodeValue(node.arguments[0]);
        if (url && isApiUrl(url)) {
            endpoints.push({ url: normalizeUrl(url), method: 'GET', confidence: 'medium', info: 'mount_path' });
        }
        return endpoints;
    }

    // app.get/post/put/delete/patch('/path', handler) -> Express routes
    const expressMatch = name.match(/^(?:app|router|server)\.(?:get|post|put|delete|patch|head|options)$/i);
    if (expressMatch && node.arguments.length >= 1) {
        const url = extractNodeValue(node.arguments[0]);
        if (url && isApiUrl(url)) {
            const httpMethod = expressMatch[1].toUpperCase();
            endpoints.push({ url: normalizeUrl(url), method: httpMethod, confidence: 'high', info: 'express-route' });
            return endpoints;
        }
    }

    // axios.all / axios.spread
    if (name === 'axios.all' || name === 'axios.spread') {
        return endpoints;
    }

    // axios.interceptors
    if (name.includes('axios.interceptors')) {
        return endpoints;
    }

    // superagent.get/post(url)
    const superagentMatch = name.match(/^(?:superagent|request)\.(?:get|post|put|delete|patch|head|options|del)$/i);
    if (superagentMatch && node.arguments.length >= 1) {
        const url = extractNodeValue(node.arguments[0]);
        if (url && isApiUrl(url)) {
            const httpMethod = superagentMatch[1].toUpperCase() === 'DEL' ? 'DELETE' : superagentMatch[1].toUpperCase();
            endpoints.push({ url: normalizeUrl(url), method: httpMethod, confidence: 'high' });
            return endpoints;
        }
    }

    // got.get/post(url) / ky.get/post(url)
    const simpleLibMatch = name.match(/^(?:got|ky|undici|needle|wreck|urllib|node-fetch)\.(?:get|post|put|delete|patch|head|options)$/i);
    if (simpleLibMatch && node.arguments.length >= 1) {
        const url = extractNodeValue(node.arguments[0]);
        if (url && isApiUrl(url)) {
            const httpMethod = simpleLibMatch[1].toUpperCase();
            endpoints.push({ url: normalizeUrl(url), method: httpMethod, confidence: 'high' });
            return endpoints;
        }
    }

    // Got/ky default export usage: got(url), ky(url)
    if ((name === 'got' || name === 'ky' || name === 'undici' || name === 'needle') && node.arguments.length >= 1) {
        const url = extractNodeValue(node.arguments[0]);
        if (url && isApiUrl(url)) {
            endpoints.push({ url: normalizeUrl(url), method: 'GET', confidence: 'high' });
            return endpoints;
        }
    }

    // request-promise / rp
    if ((name === 'request' || name === 'rp' || name === 'rpn') && node.arguments.length >= 1) {
        const first = node.arguments[0];
        if (first.type === 'ObjectExpression') {
            const url = getUrlFromObject(first);
            if (url) {
                const method = extractMethodFromOptions(node.arguments);
                endpoints.push({ url: normalizeUrl(url), method, confidence: 'high' });
            }
        } else {
            const url = extractNodeValue(first);
            if (url && isApiUrl(url)) {
                endpoints.push({ url: normalizeUrl(url), method: 'GET', confidence: 'high' });
            }
        }
        return endpoints;
    }

    // axios.get/post with destructured response
    // Rest Client (VSCode REST Client format in .http files)

    // Angular HttpClient
    const angularMatch = name.match(/^(?:this\.)?(?:httpClient|http)\.(?:get|post|put|delete|patch|head|options|request)$/i);
    if (angularMatch && node.arguments.length >= 1) {
        const httpMethod = angularMatch[1] === 'request' ? 'GET' : angularMatch[1].toUpperCase();
        let url;
        if (angularMatch[1] === 'request' && node.arguments.length >= 2) {
            // .request(method, url, options)
            const methodVal = extractNodeValue(node.arguments[0]);
            url = extractNodeValue(node.arguments[1]);
            if (methodVal) httpMethod = methodVal.toUpperCase();
        } else {
            url = extractNodeValue(node.arguments[0]);
        }
        if (url && isApiUrl(url)) {
            endpoints.push({ url: normalizeUrl(url), method: httpMethod, confidence: 'high' });
            return endpoints;
        }
    }

    // React Query / TanStack Query: useQuery({queryKey, queryFn})
    if (name === 'useQuery' || name === 'useMutation' || name === 'useInfiniteQuery') {
        if (node.arguments.length >= 1 && node.arguments[0].type === 'ObjectExpression') {
            const queryKey = getStringFromObject(node.arguments[0], ['queryKey']);
            const mutationKey = getStringFromObject(node.arguments[0], ['mutationKey']);
            const url = queryKey || mutationKey;
            if (url && isApiUrl(url)) {
                endpoints.push({ url: normalizeUrl(url), method: name === 'useMutation' ? 'POST' : 'GET', confidence: 'medium', info: 'react-query' });
            }
        }
        return endpoints;
    }

    // SWR: useSWR(key, fetcher)
    if (name === 'useSWR' || name === 'useSWRImmutable' || name === 'useSWRInfinite') {
        if (node.arguments.length >= 1) {
            const url = extractNodeValue(node.arguments[0]);
            if (url && isApiUrl(url)) {
                endpoints.push({ url: normalizeUrl(url), method: 'GET', confidence: 'medium', info: 'swr' });
            }
        }
        return endpoints;
    }

    // tRPC createTRPCReact / createTRPCClient
    if (name === 'createTRPCReact' || name === 'createTRPCClient' || name === 'createTRPCProxyClient') {
        if (node.arguments.length >= 1 && node.arguments[0].type === 'ObjectExpression') {
            const links = getStringFromObject(node.arguments[0], ['links']);
            if (!links) {
                // Check for httpBatchLink or httpLink inside links array
                for (const prop of node.arguments[0].properties) {
                    if (prop.key.name === 'links' && prop.value.type === 'ArrayExpression') {
                        for (const el of prop.value.elements) {
                            if (el.type === 'CallExpression') {
                                const calleeName = getCalleeChain(el.callee).chain.join('.');
                                if (calleeName === 'httpBatchLink' || calleeName === 'httpLink' || calleeName === 'wsLink' || calleeName === 'splitLink') {
                                    if (el.arguments.length >= 1 && el.arguments[0].type === 'ObjectExpression') {
                                        const url = getStringFromObject(el.arguments[0], ['url']);
                                        if (url) {
                                            endpoints.push({ url: normalizeUrl(url), method: 'GET', confidence: 'high', info: `trpc-${calleeName}` });
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        return endpoints;
    }

    // tRPC proxy query/mutate
    const trpcCallMatch = name.match(/^(.+)\.(query|mutate|subscribe)$/i);
    if (trpcCallMatch && (trpcCallMatch[1].includes('trpc') || trpcCallMatch[1].includes('client'))) {
        if (node.arguments.length >= 1) {
            const url = extractNodeValue(node.arguments[0]);
            if (url) {
                const segments = trpcCallMatch[1].split('.');
                // Build URL path from chained calls: trpc.user.list.query() -> /user/list
                const path = '/' + segments.slice(1).join('/').toLowerCase();
                endpoints.push({ url: path, method: trpcCallMatch[2].toUpperCase() === 'QUERY' ? 'GET' : 'POST', confidence: 'medium', info: 'trpc-proxy' });
            }
        }
        return endpoints;
    }

    // Apollo useQuery / useMutation (via AST, but also check CallExpression wrapping)
    // Already handled by gql patterns in SDK patterns

    // fetchEvent.respondWith (service worker)
    if (name === 'event.respondWith' || name === 'e.respondWith' || name === 'evt.respondWith') {
        return endpoints; // Will be handled by regex patterns
    }

    // caches.open / cache.addAll
    if (name === 'caches.open') {
        if (node.arguments.length >= 1) {
            const url = extractNodeValue(node.arguments[0]);
            if (url && isApiUrl(url)) {
                endpoints.push({ url: normalizeUrl(url), method: 'GET', confidence: 'medium', info: 'sw-cache' });
            }
        }
        return endpoints;
    }

    // cache.add(url)
    if (name === 'cache.add' && node.arguments.length >= 1) {
        const url = extractNodeValue(node.arguments[0]);
        if (url && isApiUrl(url)) {
            endpoints.push({ url: normalizeUrl(url), method: 'GET', confidence: 'medium', info: 'sw-cache-add' });
        }
        return endpoints;
    }

    // navigator.sendBeacon(url)
    if (name === 'navigator.sendBeacon' && node.arguments.length >= 1) {
        const url = extractNodeValue(node.arguments[0]);
        if (url && isApiUrl(url)) {
            endpoints.push({ url: normalizeUrl(url), method: 'POST', confidence: 'high', info: 'sendBeacon' });
            return endpoints;
        }
    }

    // XMLHttpRequest
    if (name === 'XMLHttpRequest.open' || name === 'xhr.open' || name === 'req.open' || name === 'request.open') {
        if (node.arguments.length >= 2) {
            const method = extractNodeValue(node.arguments[0]);
            const url = extractNodeValue(node.arguments[1]);
            if (url && isApiUrl(url)) {
                endpoints.push({ url: normalizeUrl(url), method: (method || 'GET').toUpperCase(), confidence: 'high', info: 'xhr' });
                return endpoints;
            }
        }
    }

    // new XMLHttpRequest() with separate open() call - handled by regex

    // Service worker clients.openWindow
    if (name === 'clients.openWindow' && node.arguments.length >= 1) {
        const url = extractNodeValue(node.arguments[0]);
        if (url && isApiUrl(url)) {
            endpoints.push({ url: normalizeUrl(url), method: 'GET', confidence: 'medium', info: 'sw-openWindow' });
        }
        return endpoints;
    }

    // location.assign / location.replace
    if ((name === 'location.assign' || name === 'location.replace' || name === 'window.location.assign' || name === 'window.location.replace') && node.arguments.length >= 1) {
        const url = extractNodeValue(node.arguments[0]);
        if (url && isApiUrl(url)) {
            endpoints.push({ url: normalizeUrl(url), method: 'GET', confidence: 'low', info: 'location' });
        }
        return endpoints;
    }

    // window.open(url)
    if (name === 'window.open' && node.arguments.length >= 1) {
        const url = extractNodeValue(node.arguments[0]);
        if (url && isApiUrl(url)) {
            endpoints.push({ url: normalizeUrl(url), method: 'GET', confidence: 'low', info: 'window-open' });
        }
        return endpoints;
    }

    // history.pushState / history.replaceState
    if ((name === 'history.pushState' || name === 'history.replaceState') && node.arguments.length >= 3) {
        const url = extractNodeValue(node.arguments[2]);
        if (url && isApiUrl(url)) {
            endpoints.push({ url: normalizeUrl(url), method: 'GET', confidence: 'low', info: 'history' });
        }
        return endpoints;
    }

    // Form action submission programmatically
    // form.submit()

    // window.fetch (same as fetch)
    if (name === 'window.fetch' && node.arguments.length >= 1) {
        const url = extractNodeValue(node.arguments[0]);
        if (url && isApiUrl(url)) {
            const method = extractMethodFromOptions(node.arguments);
            endpoints.push({ url: normalizeUrl(url), method, confidence: 'high', info: 'window-fetch' });
            return endpoints;
        }
    }

    // cross-fetch / isomorphic-fetch / node-fetch
    // These are usually imported and used as fetch

    return endpoints;
}

function extractFromNewExpression(node) {
    if (node.callee.type !== 'Identifier') {
        // Handle e.g. new firebase.auth.GoogleAuthProvider()
        if (node.callee.type === 'MemberExpression') {
            const chain = getCalleeChain(node.callee);
            const name = chain.chain.join('.');
            // Firebase auth providers
            if (/firebase\.auth\.\w+Provider/.test(name)) {
                return [];
            }
        }
        return [];
    }

    const name = node.callee.name;
    const urls = [];

    // WebSocket / EventSource / Worker / SharedWorker
    if (['WebSocket', 'EventSource', 'Worker', 'SharedWorker'].includes(name)) {
        if (node.arguments.length >= 1) {
            const url = extractNodeValue(node.arguments[0]);
            if (url && isApiUrl(url)) {
                urls.push({ url: normalizeUrl(url), method: 'GET', confidence: 'high', info: name.toLowerCase() });
            }
        }
        return urls;
    }

    // AbortController / AbortSignal
    if (name === 'AbortController' || name === 'AbortSignal') {
        return urls;
    }

    // Headers
    if (name === 'Headers' || name === 'Request' || name === 'Response') {
        return urls;
    }

    // FormData
    if (name === 'FormData' || name === 'URLSearchParams') {
        return urls;
    }

    // URL constructor
    if (name === 'URL' && node.arguments.length >= 1) {
        const url = extractNodeValue(node.arguments[0]);
        if (url && isApiUrl(url)) {
            urls.push({ url: normalizeUrl(url), method: 'GET', confidence: 'medium', info: 'url-ctor' });
        }
        return urls;
    }

    // URLPattern
    if (name === 'URLPattern' && node.arguments.length >= 1) {
        const pattern = extractNodeValue(node.arguments[0]);
        if (pattern && isApiUrl(pattern)) {
            urls.push({ url: normalizeUrl(pattern), method: 'GET', confidence: 'medium', info: 'url-pattern' });
        }
        return urls;
    }

    // Image constructor (for tracking pixels / GET requests)
    if (name === 'Image' && node.arguments.length === 0) {
        // Often used as: new Image(); img.src = url;
        return urls;
    }

    // Audio constructor
    if (name === 'Audio') {
        return urls;
    }

    // MutationObserver / IntersectionObserver / ResizeObserver
    if (['MutationObserver', 'IntersectionObserver', 'ResizeObserver', 'PerformanceObserver'].includes(name)) {
        return urls;
    }

    // PushManager
    if (name === 'PushManager') {
        return urls;
    }

    // Notification
    if (name === 'Notification') {
        return urls;
    }

    // ServiceWorkerRegistration
    if (name === 'ServiceWorkerRegistration') {
        return urls;
    }

    // PaymentRequest
    if (name === 'PaymentRequest') {
        return urls;
    }

    // WebAssembly
    if (name === 'WebAssembly') {
        return urls;
    }

    // WebSocket (alternative name)
    if (name === 'WebSocketPair') {
        return urls;
    }

    return urls;
}

function extractEndpoints(jsCode, sourceFile) {
    const results = [];
    let ast;

    const parseOptions = [
        { ecmaVersion: 'latest', sourceType: 'module', locations: true, allowImportExportEverywhere: true, allowAwaitOutsideFunction: true, allowSuperOutsideMethod: true, allowReturnOutsideFunction: true },
        { ecmaVersion: 'latest', sourceType: 'script', locations: true, allowAwaitOutsideFunction: true, allowSuperOutsideMethod: true, allowReturnOutsideFunction: true },
        { ecmaVersion: 2022, sourceType: 'module', locations: true },
        { ecmaVersion: 2022, sourceType: 'script', locations: true },
        { ecmaVersion: 2021, sourceType: 'module', locations: true },
        { ecmaVersion: 2021, sourceType: 'script', locations: true },
        { ecmaVersion: 2020, sourceType: 'module', locations: true },
        { ecmaVersion: 2020, sourceType: 'script', locations: true },
        { ecmaVersion: 2019, sourceType: 'module', locations: true },
        { ecmaVersion: 2019, sourceType: 'script', locations: true },
        { ecmaVersion: 2018, sourceType: 'module', locations: true },
        { ecmaVersion: 2018, sourceType: 'script', locations: true },
    ];

    let parsed = false;
    for (const opts of parseOptions) {
        try {
            ast = acorn.parse(jsCode, opts);
            parsed = true;
            break;
        } catch (e) {
            continue;
        }
    }

    if (!parsed) {
        try {
            ast = acorn.parse(jsCode, { ecmaVersion: 'latest', sourceType: 'module', locations: true, preserveParens: true, allowImportExportEverywhere: true });
        } catch (e) {
            // If AST totally fails, use regex-based extraction as fallback
            const regexEndpoints = extractWithRegex(jsCode, sourceFile);
            return regexEndpoints;
        }
    }

    if (!ast) {
        const regexEndpoints = extractWithRegex(jsCode, sourceFile);
        return regexEndpoints;
    }

    const seen = new Set();
    const resultsFromAst = [];

    function addResult(url, method, confidence, loc, extraInfo = '') {
        if (!url) return;
        const key = `${method}:${url}`;
        if (seen.has(key)) return;
        seen.add(key);
        resultsFromAst.push({
            url,
            method,
            confidence,
            source: sourceFile || 'unknown',
            line: loc ? loc.start.line : null,
            info: extraInfo,
        });
    }

    walk.simple(ast, {
        Literal(node) {
            if (typeof node.value === 'string' && isApiUrl(node.value)) {
                addResult(normalizeUrl(node.value), 'GET', 'medium', node.loc);
            }
        },

        TemplateLiteral(node) {
            let staticParts = '';
            for (const quasi of node.quasis) {
                staticParts += quasi.value.raw;
            }
            if (isApiUrl(staticParts)) {
                let reconstructed = '';
                for (let i = 0; i < node.quasis.length; i++) {
                    reconstructed += node.quasis[i].value.raw;
                    if (i < node.expressions.length) {
                        const expr = node.expressions[i];
                        let paramName = ':param';
                        if (expr.type === 'Identifier') {
                            paramName = `:${expr.name}`;
                        } else if (expr.type === 'MemberExpression' && !expr.computed &&
                                   expr.property.type === 'Identifier') {
                            paramName = `:${expr.property.name}`;
                        } else if (expr.type === 'CallExpression') {
                            paramName = ':fn';
                        }
                        reconstructed += paramName;
                    }
                }
                addResult(normalizeUrl(reconstructed), 'GET', 'medium', node.loc, 'template_literal');
            }
        },

        CallExpression(node) {
            const callee = getCalleeChain(node.callee);
            const extracted = extractFromCall(node, callee);
            for (const ep of extracted) {
                addResult(ep.url, ep.method, ep.confidence, node.loc, ep.info || '');
            }
        },

        NewExpression(node) {
            const extracted = extractFromNewExpression(node);
            for (const ep of extracted) {
                addResult(ep.url, ep.method, ep.confidence, node.loc, ep.info);
            }
        },

        VariableDeclarator(node) {
            if (node.init && node.id.type === 'Identifier') {
                const name = node.id.name.toLowerCase();
                if (/^(api_url|api_uri|base_url|base_uri|endpoint|service_url|rest_url|graphql_url|backend_url|server_url|cdn_url|upload_url|download_url|stream_url|ws_url|websocket_url|sse_url|events_url|webhook_url|callback_url|redirect_url|proxy_url|gateway_url|function_url|hook_url|notification_url|push_url)/i.test(name)) {
                    const val = extractNodeValue(node.init);
                    if (val && isApiUrl(val)) {
                        addResult(normalizeUrl(val), 'GET', 'high', node.loc, `var:${node.id.name}`);
                    }
                }
            }
            // Destructured assignment: const { url } = someObject
            if (node.init && node.id.type === 'ObjectPattern') {
                for (const prop of node.id.properties) {
                    if (prop.type === 'Property' && prop.key.type === 'Identifier') {
                        const keyName = prop.key.name.toLowerCase();
                        if (['url', 'endpoint', 'baseurl', 'base_url', 'apiurl', 'api_url'].includes(keyName)) {
                            const val = extractNodeValue(node.init);
                            // Can't easily extract from destructured init, skip
                        }
                    }
                }
            }
        },

        AssignmentExpression(node) {
            if (node.right.type === 'Literal' && typeof node.right.value === 'string') {
                let name = '';
                if (node.left.type === 'MemberExpression' && !node.left.computed &&
                    node.left.property.type === 'Identifier') {
                    name = node.left.property.name;
                } else if (node.left.type === 'Identifier') {
                    name = node.left.name;
                }
                if (/^(api_url|api_uri|base_url|base_uri|endpoint|service_url|rest_url|graphql_url|backend_url|server_url|cdn_url|upload_url|download_url|stream_url|ws_url|websocket_url|sse_url|events_url|webhook_url|callback_url|redirect_url|proxy_url|gateway_url|function_url|hook_url|notification_url|push_url|src|href|action|url|uri)/i.test(name)) {
                    if (isApiUrl(node.right.value)) {
                        addResult(normalizeUrl(node.right.value), 'GET', 'high', node.loc, `assign:${name}`);
                    }
                }
            }
            // Member expression assignment: obj.url = '...'
            if (node.right.type === 'Literal' && typeof node.right.value === 'string') {
                if (node.left.type === 'MemberExpression' && node.left.property.type === 'Identifier') {
                    const propName = node.left.property.name.toLowerCase();
                    if (['url', 'endpoint', 'baseurl', 'base_url', 'apiurl', 'api_url', 'src', 'href', 'action'].includes(propName)) {
                        if (isApiUrl(node.right.value)) {
                            addResult(normalizeUrl(node.right.value), 'GET', 'medium', node.loc, `member-assign:${propName}`);
                        }
                    }
                }
            }
        },

        Property(node) {
            const key = node.key.type === 'Identifier' ? node.key.name :
                        node.key.type === 'Literal' ? node.key.value : null;
            if (key) {
                const k = key.toString().toLowerCase();
                if (['url', 'endpoint', 'baseurl', 'base_url', 'apiurl', 'api_url',
                     'target', 'path', 'uri', 'href', 'src', 'action', 'redirect',
                     'callback', 'webhook', 'webhook_url', 'callback_url',
                     'upload_url', 'download_url', 'stream_url', 'sse_url',
                     'ws_url', 'wss_url', 'websocket', 'events_url',
                     'service_url', 'server_url', 'backend_url',
                     'function_url', 'gateway_url', 'proxy_url',
                     'notification_url', 'push_url', 'image_url',
                     'file_url', 'avatar_url', 'profile_url',
                     'collection', 'self', 'next', 'prev', 'first', 'last',
                     'edit', 'create', 'update', 'delete', 'patch',
                     'login_url', 'register_url', 'logout_url',
                     'verify_url', 'reset_url', 'forgot_url',
                     'docs_url', 'api_docs', 'documentation_url',
                     'basepath', 'base_path'].includes(k)) {
                    const val = extractNodeValue(node.value);
                    if (val && isApiUrl(val)) {
                        addResult(normalizeUrl(val), 'GET', 'medium', node.loc, `prop:${key}`);
                    }
                }
            }
        },

        // SpreadElement - check if spread object contains URL properties
        // Already covered by other visitors

        // ImportDeclaration - detect imported APIs
        ImportDeclaration(node) {
            const source = node.source && node.source.value;
            if (source && typeof source === 'string') {
                if (isApiUrl(source)) {
                    addResult(normalizeUrl(source), 'GET', 'medium', node.loc, 'import');
                }
            }
        },

        // ExportNamedDeclaration / ExportAllDeclaration
        ExportNamedDeclaration(node) {
            if (node.source && node.source.value && typeof node.source.value === 'string') {
                if (isApiUrl(node.source.value)) {
                    addResult(normalizeUrl(node.source.value), 'GET', 'medium', node.loc, 'export');
                }
            }
        },

        ExportAllDeclaration(node) {
            if (node.source && node.source.value && typeof node.source.value === 'string') {
                if (isApiUrl(node.source.value)) {
                    addResult(normalizeUrl(node.source.value), 'GET', 'medium', node.loc, 'export-all');
                }
            }
        },

        // ReturnStatement - check for API URL returns
        ReturnStatement(node) {
            if (node.argument && node.argument.type === 'Literal' && typeof node.argument.value === 'string') {
                if (isApiUrl(node.argument.value)) {
                    addResult(normalizeUrl(node.argument.value), 'GET', 'medium', node.loc, 'return');
                }
            }
        },

        // ArrowFunctionExpression - check single-expression body
        ArrowFunctionExpression(node) {
            if (node.expression && node.body && node.body.type === 'Literal' && typeof node.body.value === 'string') {
                if (isApiUrl(node.body.value)) {
                    addResult(normalizeUrl(node.body.value), 'GET', 'medium', node.loc, 'arrow');
                }
            }
        },

        // TaggedTemplateExpression - e.g. GraphQL tagged templates
        TaggedTemplateExpression(node) {
            const tagName = node.tag.type === 'Identifier' ? node.tag.name :
                node.tag.type === 'MemberExpression' ? getCalleeChain(node.tag).chain.join('.') : '';
            // Check for graphql`...` or gql`...` tagged templates
            if (tagName === 'graphql' || tagName === 'gql') {
                let staticParts = '';
                for (const quasi of node.quasi.quasis) {
                    staticParts += quasi.value.raw;
                }
                // Extract operation names from the template
                const ops = (staticParts.match(/(?:query|mutation|subscription)\s+(\w+)/gi) || []);
                for (const op of ops) {
                    const parts = op.split(/\s+/);
                    if (parts.length >= 2) {
                        addResult('/' + parts[1].toLowerCase(), parts[0].toUpperCase() === 'MUTATION' ? 'POST' : 'GET', 'medium', node.loc, 'gql-tag');
                    }
                }
            }
        },
    });

    // Combine AST results
    for (const r of resultsFromAst) {
        results.push(r);
    }

    // Run SDK pattern extraction as fallback (catches things AST might miss)
    const sdkEndpoints = extractSDKPatterns(jsCode, sourceFile);
    for (const ep of sdkEndpoints) {
        const key = `${ep.method}:${ep.url}`;
        if (!seen.has(key)) {
            seen.add(key);
            results.push(ep);
        }
    }

    // GraphQL operation extraction from raw string patterns
    const gqlOps = extractGraphQLOperations(jsCode);
    for (const op of gqlOps) {
        const key = `${op.method}:${op.url}`;
        if (!seen.has(key)) {
            seen.add(key);
            results.push({
                url: op.url,
                method: op.method,
                confidence: op.confidence,
                source: sourceFile || 'unknown',
                line: null,
                info: op.type || 'graphql-op',
            });
        }
    }

    return results;
}

// Regex-based fallback for code that fails AST parsing
function extractWithRegex(jsCode, sourceFile) {
    const results = [];
    const seen = new Set();

    function add(url, method, confidence, info = '') {
        if (!url) return;
        const key = `${method}:${url}`;
        if (seen.has(key)) return;
        seen.add(key);
        results.push({
            url: normalizeUrl(url),
            method,
            confidence,
            source: sourceFile || 'unknown',
            line: null,
            info: info || 'regex-fallback',
        });
    }

    // URL strings
    const urlRegex = /['"`](https?:\/\/[^\s'"`]+)['"`]/g;
    let m;
    while ((m = urlRegex.exec(jsCode)) !== null) {
        if (isApiUrl(m[1])) add(m[1], 'GET', 'low', 'regex-url');
    }

    // Relative API paths
    const pathRegex = /['"`](\/[^\s'"`]*(?:api|v\d|graphql|rest|swagger|openapi)[^\s'"`]*)['"`]/gi;
    while ((m = pathRegex.exec(jsCode)) !== null) {
        add(m[1], 'GET', 'low', 'regex-path');
    }

    // fetch/axios calls
    const fetchRegex = /(?:fetch|axios|getJSON|ajax|ky|got)\s*\(?\s*['"`]([^\s'"`]+)['"`]/gi;
    while ((m = fetchRegex.exec(jsCode)) !== null) {
        if (isApiUrl(m[1])) add(m[1], 'GET', 'medium', 'regex-fetch');
    }

    // fetch/axios with method
    const methodFetchRegex = /(?:fetch|axios)\(['"`]([^\s'"`]+)['"`]\s*,\s*\{[^}]*method:\s*['"`](\w+)['"`]/gi;
    while ((m = methodFetchRegex.exec(jsCode)) !== null) {
        if (isApiUrl(m[1])) add(m[1], m[2].toUpperCase(), 'medium', 'regex-fetch-method');
    }

    // axios.get/post/put/delete/patch
    const axiosMethodRegex = /axios\.(get|post|put|delete|patch|head|options)\(['"`]([^\s'"`]+)['"`]/gi;
    while ((m = axiosMethodRegex.exec(jsCode)) !== null) {
        if (isApiUrl(m[2])) add(m[2], m[1].toUpperCase(), 'medium', 'regex-axios-method');
    }

    // WebSocket/EventSource
    const wsRegex = /(?:new\s+)?(?:WebSocket|EventSource)\(['"`]([^\s'"`]+)['"`]/gi;
    while ((m = wsRegex.exec(jsCode)) !== null) {
        add(m[1], 'GET', 'medium', 'regex-ws');
    }

    // SDK patterns
    const sdkEndpoints = extractSDKPatterns(jsCode, sourceFile);
    for (const ep of sdkEndpoints) {
        add(ep.url, ep.method, ep.confidence, ep.info);
    }

    // GraphQL gql``
    const gqlRegex = /gql`([^`]+)`/g;
    while ((m = gqlRegex.exec(jsCode)) !== null) {
        const ops = m[1].match(/(?:query|mutation|subscription)\s+(\w+)/gi) || [];
        for (const op of ops) {
            const parts = op.split(/\s+/);
            if (parts.length >= 2) {
                add('/' + parts[1].toLowerCase(), parts[0].toUpperCase() === 'MUTATION' ? 'POST' : 'GET', 'medium', 'regex-gql');
            }
        }
    }

    // tRPC patterns
    const trpcRegex = /httpBatchLink\(\{[^}]*url:\s*['"`]([^\s'"`]+)['"`]/gi;
    while ((m = trpcRegex.exec(jsCode)) !== null) {
        add(m[1], 'GET', 'medium', 'regex-trpc');
    }

    return results;
}

function main() {
    let jsCode = '';

    if (process.argv[2]) {
        const filePath = process.argv[2];
        try {
            jsCode = fs.readFileSync(filePath, 'utf8');
        } catch (e) {
            console.error(JSON.stringify({ error: `Cannot read file: ${filePath}` }));
            process.exit(1);
        }
    } else {
        const chunks = [];
        process.stdin.setEncoding('utf8');
        process.stdin.on('data', chunk => chunks.push(chunk));
        process.stdin.on('end', () => {
            jsCode = chunks.join('');
            const results = extractEndpoints(jsCode, 'stdin');
            console.log(JSON.stringify(results));
        });
        return;
    }

    const sourceLabel = process.argv[3] || path.basename(process.argv[2]);
    const results = extractEndpoints(jsCode, sourceLabel);
    console.log(JSON.stringify(results));
}

if (require.main === module) {
    main();
}

module.exports = { extractEndpoints, isApiUrl, normalizeUrl, extractSDKPatterns, extractGraphQLOperations };
