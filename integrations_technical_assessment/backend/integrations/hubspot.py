# slack.py

import json
import secrets
import base64
import os
from dotenv import load_dotenv
from fastapi import Request, HTTPException
from fastapi.responses import HTMLResponse
import httpx
import asyncio
import requests
from integrations.integration_item import IntegrationItem

from redis_client import add_key_value_redis, get_value_redis, delete_key_redis

load_dotenv()

CLIENT_ID = os.getenv('HUBSPOT_CLIENT_ID')
CLIENT_SECRET = os.getenv('HUBSPOT_CLIENT_SECRET')
REDIRECT_URI = os.getenv('HUBSPOT_REDIRECT_URI')
SCOPES = ' '.join([
    'crm.objects.contacts.read',
    'crm.objects.contacts.write', 
    'crm.objects.deals.read',
    'crm.schemas.contacts.read'
])

async def authorize_hubspot(user_id, org_id):
    if not CLIENT_ID or not CLIENT_SECRET:
        raise HTTPException(status_code=500, detail="HubSpot credentials not configured")
    
    print("DEBUG: Using Client ID:", CLIENT_ID)
    print("DEBUG: Using Redirect URI:", REDIRECT_URI)
    
    state_data = {
        'state': secrets.token_urlsafe(32),
        'user_id': user_id,
        'org_id': org_id
    }
    # Encode state same way as Airtable
    encoded_state = base64.urlsafe_b64encode(json.dumps(state_data).encode('utf-8')).decode('utf-8')
    await add_key_value_redis(f'hubspot_state:{org_id}:{user_id}', json.dumps(state_data), expire=600)
    
    auth_url = (
        f'https://app.hubspot.com/oauth/authorize'
        f'?client_id={CLIENT_ID}'
        f'&redirect_uri={REDIRECT_URI}'
        f'&scope={SCOPES}'
        f'&state={encoded_state}'
    )
    print("DEBUG: Generated auth URL:", auth_url)
    return auth_url

async def oauth2callback_hubspot(request: Request):
    try:
        print("DEBUG: Received callback with params:", dict(request.query_params))
        
        if request.query_params.get('error'):
            raise HTTPException(status_code=400, detail=request.query_params.get('error_description'))
        
        code = request.query_params.get('code')
        encoded_state = request.query_params.get('state')

        # Decode state same way as Airtable
        state_data = json.loads(base64.urlsafe_b64decode(encoded_state).decode('utf-8'))
        
        user_id = state_data.get('user_id') 
        org_id = state_data.get('org_id')
        original_state = state_data.get('state')

        saved_state = await get_value_redis(f'hubspot_state:{org_id}:{user_id}')
        if not saved_state or original_state != json.loads(saved_state).get('state'):
            raise HTTPException(status_code=400, detail='State mismatch')

        async with httpx.AsyncClient() as client:
            response, _ = await asyncio.gather(
                client.post(
                    'https://api.hubapi.com/oauth/v1/token',
                    data={
                        'grant_type': 'authorization_code',
                        'client_id': CLIENT_ID,
                        'client_secret': CLIENT_SECRET,
                        'redirect_uri': REDIRECT_URI,
                        'code': code
                    },
                    headers={'Content-Type': 'application/x-www-form-urlencoded'}
                ),
                delete_key_redis(f'hubspot_state:{org_id}:{user_id}')
            )

        await add_key_value_redis(
            f'hubspot_credentials:{org_id}:{user_id}', 
            json.dumps(response.json()), 
            expire=600
        )
        
        return HTMLResponse(content='<html><script>window.close();</script></html>')
        
    except Exception as e:
        print("DEBUG: OAuth error:", str(e))
        raise HTTPException(status_code=400, detail=f'OAuth failed: {str(e)}')

async def get_hubspot_credentials(user_id, org_id):
    credentials = await get_value_redis(f'hubspot_credentials:{org_id}:{user_id}')
    if not credentials:
        raise HTTPException(status_code=400, detail='No credentials found.')
    credentials = json.loads(credentials)
    await delete_key_redis(f'hubspot_credentials:{org_id}:{user_id}')
    return credentials

async def create_integration_item_metadata_object(response_json):
    """Creates an integration metadata object from the HubSpot response"""
    integration_item_metadata = IntegrationItem(
        id=response_json.get('id'),
        type='contact',  # Can be expanded to handle different HubSpot object types
        name=f"{response_json.get('properties', {}).get('firstname', '')} {response_json.get('properties', {}).get('lastname', '')}",
        creation_time=response_json.get('createdAt'),
        last_modified_time=response_json.get('updatedAt'),
        # Additional fields can be added based on HubSpot's object properties
        url=f"https://app.hubspot.com/contacts/{response_json.get('id')}",
    )
    return integration_item_metadata

async def get_items_hubspot(credentials):
    """
    Fetch contacts and deals from HubSpot and return as IntegrationItem objects
    """
    credentials = json.loads(credentials)
    access_token = credentials.get('access_token')
    
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    
    items = []
    
    # Fetch Contacts
    try:
        contacts_response = requests.get(
            'https://api.hubapi.com/crm/v3/objects/contacts',
            headers=headers,
            params={'limit': 100}  # Adjust limit as needed
        )
        
        if contacts_response.status_code == 200:
            contacts_data = contacts_response.json()
            print("DEBUG: Retrieved contacts:", len(contacts_data.get('results', [])))
            
            for contact in contacts_data.get('results', []):
                props = contact.get('properties', {})
                item = IntegrationItem(
                    id=f"contact_{contact.get('id')}",
                    type='contact',
                    name=f"{props.get('firstname', '')} {props.get('lastname', '')}",
                    creation_time=props.get('createdate'),
                    last_modified_time=props.get('lastmodifieddate'),
                    url=f"https://app.hubspot.com/contacts/{contact.get('id')}",
                    parent_path_or_name='Contacts',
                    visibility=True
                )
                items.append(item)
    
        # Fetch Deals
        deals_response = requests.get(
            'https://api.hubapi.com/crm/v3/objects/deals',
            headers=headers,
            params={'limit': 100}
        )
        
        if deals_response.status_code == 200:
            deals_data = deals_response.json()
            print("DEBUG: Retrieved deals:", len(deals_data.get('results', [])))
            
            for deal in deals_data.get('results', []):
                props = deal.get('properties', {})
                item = IntegrationItem(
                    id=f"deal_{deal.get('id')}",
                    type='deal',
                    name=props.get('dealname', 'Unnamed Deal'),
                    creation_time=props.get('createdate'),
                    last_modified_time=props.get('lastmodifieddate'),
                    url=f"https://app.hubspot.com/deals/{deal.get('id')}",
                    parent_path_or_name='Deals',
                    visibility=True,
                    # Add deal-specific fields
                    children=[
                        f"Amount: ${props.get('amount', '0')}",
                        f"Stage: {props.get('dealstage', 'Unknown')}"
                    ]
                )
                items.append(item)

        # Print results to console
        print("\nRetrieved HubSpot Items:")
        for item in items:
            print(f"\nType: {item.type}")
            print(f"Name: {item.name}")
            print(f"Created: {item.creation_time}")
            print(f"URL: {item.url}")
            if item.children:
                print("Details:", item.children)
            print("-" * 50)

        return items

    except Exception as e:
        print("DEBUG: Error fetching HubSpot data:", str(e))
        raise HTTPException(status_code=500, detail=f'Failed to fetch HubSpot data: {str(e)}')