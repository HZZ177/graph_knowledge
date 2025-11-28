import React from 'react'
import { createBrowserRouter } from 'react-router-dom'
import MainLayout from './layouts/MainLayout'
import HomePage from './pages/HomePage'
import ResourceLibraryPage from './pages/ResourceLibraryPage'
import BusinessLibraryPage from './pages/BusinessLibraryPage'
import LLMModelManagePage from './pages/LLMModelManagePage'
import ChatPage from './pages/ChatPage'

const router = createBrowserRouter([
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
        path: '/llm-models',
        element: <LLMModelManagePage />,
      },
    ],
  },
])

export default router
