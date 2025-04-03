import { useState, useEffect } from 'react';
import {
    Box,
    Button,
    CircularProgress
} from '@mui/material';
import axios from 'axios';

export const HubspotIntegration = ({ user, org, integrationParams, setIntegrationParams }) => {
    const [isConnected, setIsConnected] = useState(false);
    const [isConnecting, setIsConnecting] = useState(false);

    const handleConnectClick = async () => {
        try {
            setIsConnecting(true);
            const formData = new FormData();
            formData.append('user_id', user);
            formData.append('org_id', org);
            
            const response = await axios.post('http://localhost:8000/integrations/hubspot/authorize', formData);
            const authURL = response?.data;
            
            // Update popup window options
            const width = 600;
            const height = 700;
            const left = (window.innerWidth - width) / 2;
            const top = (window.innerHeight - height) / 2;
            
            const popup = window.open(
                authURL,
                'HubSpot Authorization',
                `width=${width},height=${height},left=${left},top=${top},toolbar=0,location=0,status=0,menubar=0`
            );
            
            if (!popup) {
                alert('Please allow popups for this site');
                setIsConnecting(false);
                return;
            }

            // Check both popup closed and URL changes
            const pollTimer = setInterval(() => {
                try {
                    if (popup.closed) {
                        clearInterval(pollTimer);
                        handleWindowClosed();
                    }
                } catch (e) {
                    clearInterval(pollTimer);
                    setIsConnecting(false);
                }
            }, 500);

        } catch (e) {
            console.error("Connection error:", e);
            setIsConnecting(false);
            alert(e?.response?.data?.detail || 'Connection failed. Please try again.');
        }
    }

    const handleWindowClosed = async () => {
        try {
            const formData = new FormData();
            formData.append('user_id', user);
            formData.append('org_id', org);
            
            const response = await axios.post('http://localhost:8000/integrations/hubspot/credentials', formData, {
                headers: {
                    'Accept': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                withCredentials: false
            });
            
            const credentials = response.data;
            if (credentials) {
                setIsConnecting(false);  
                setIsConnected(true);
                setIntegrationParams(prev => ({ ...prev, credentials: credentials, type: 'Hubspot' }));
            }
            setIsConnecting(false);
        } catch (e) {
            setIsConnecting(false);
            alert(e?.response?.data?.detail || 'Failed to get credentials');
        }
    }

    useEffect(() => {
        setIsConnected(integrationParams?.credentials ? true : false)
    }, []);

    return (
        <>
        <Box sx={{mt: 2}}>
            Parameters
            <Box display='flex' alignItems='center' justifyContent='center' sx={{mt: 2}}>
                <Button 
                    variant='contained' 
                    onClick={isConnected ? () => {} : handleConnectClick}
                    color={isConnected ? 'success' : 'primary'}
                    disabled={isConnecting}
                    style={{
                        pointerEvents: isConnected ? 'none' : 'auto',
                        cursor: isConnected ? 'default' : 'pointer',
                        opacity: isConnected ? 1 : undefined
                    }}
                >
                    {isConnected ? 'HubSpot Connected' : isConnecting ? <CircularProgress size={20} /> : 'Connect to HubSpot'}
                </Button>
            </Box>
        </Box>
      </>
    );
}
