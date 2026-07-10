"use client";
import { ApolloClient, InMemoryCache } from "@apollo/client";
import { ApolloNextAppProvider } from "@apollo/experimental-nextjs-app-support";

function makeClient() {
  return new ApolloClient({
    uri: "/graphql",
    cache: new InMemoryCache(),
  });
}

export function ApolloWrapper({ children }) {
  return (
    <ApolloNextAppProvider makeClient={makeClient}>
      {children}
    </ApolloNextAppProvider>
  );
}
