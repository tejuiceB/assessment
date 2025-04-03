import { useState } from 'react';
import {
    Box,
    TextField,
    Button,
} from '@mui/material';
import axios from 'axios';

const endpointMapping = {
    'Notion': 'notion/load',
    'Airtable': 'airtable/load',
    'Hubspot': 'hubspot/load'  // Just /load, not /load/load
};

export const DataForm = ({ integrationType, credentials }) => {
    const [loadedData, setLoadedData] = useState(null);
    const endpoint = endpointMapping[integrationType];

    const handleLoad = async () => {
        try {
            const formData = new FormData();
            formData.append('credentials', JSON.stringify(credentials));
            
            // Log for debugging
            console.log("Loading data from:", `http://localhost:8000/integrations/${endpoint}`);
            console.log("With credentials:", credentials);
            
            const response = await axios.post(`http://localhost:8000/integrations/${endpoint}`, formData);
            const data = response.data;
            setLoadedData(JSON.stringify(data, null, 2)); // Pretty print the JSON data
        } catch (e) {
            console.error("Load error:", e);
            alert(e?.response?.data?.detail || 'Failed to load data');
        }
    }

    return (
        <Box display='flex' justifyContent='center' alignItems='center' flexDirection='column' width='100%'>
            <Box display='flex' flexDirection='column' width='100%'>
                <TextField
                    label="Loaded Data"
                    value={loadedData || ''}
                    sx={{mt: 2}}
                    InputLabelProps={{ shrink: true }}
                    disabled
                />
                <Button
                    onClick={handleLoad}
                    sx={{mt: 2}}
                    variant='contained'
                >
                    Load Data
                </Button>
                <Button
                    onClick={() => setLoadedData(null)}
                    sx={{mt: 1}}
                    variant='contained'
                >
                    Clear Data
                </Button>
            </Box>
        </Box>
    );
}
