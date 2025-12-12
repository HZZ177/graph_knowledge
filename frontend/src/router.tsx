import React from 'react'
import { createBrowserRouter } from 'react-router-dom'
import MainLayout from './layouts/MainLayout'
import HomePage from './pages/HomePage'
import ResourceLibraryPage from './pages/ResourceLibraryPage'
import BusinessLibraryPage from './pages/BusinessLibraryPage'
import LLMModelManagePage from './pages/LLMModelManagePage'
import ChatPage from './pages/ChatPage'
import DocCenterPage from './pages/DocCenterPage'

const router = createBrowserRouter(
  [
    {
      path: '/',
      element: <MainLayout />,
      children: [
        {
          index: true,
          element: <HomePage />,
        },
        {
          path: '/chat',
          element: <ChatPage />,
        },
        {
          path: '/resources',
          element: <ResourceLibraryPage />,
        },
        {
          path: '/business',
          element: <BusinessLibraryPage />,
        },
        {
          path: '/doc-center',
          element: <DocCenterPage />,
        },
        {
          path: '/llm-models',
          element: <LLMModelManagePage />,
        },
      ],
    },
  ],
  {
    future: {
      v7_startTransition: true,
      v7_relativeSplatPath: true,
    } as any,  // React Router v7 future flags
  }
)

export default router
