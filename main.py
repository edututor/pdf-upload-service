from fastapi import FastAPI, UploadFile, Form
from fastapi.responses import JSONResponse
from botocore.exceptions import NoCredentialsError
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
from fastapi.middleware.cors import CORSMiddleware
from config import settings
from loguru import logger
import os
import boto3


app = FastAPI()
# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Frontend origin
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods (POST, GET, etc.)
    allow_headers=["*"],  # Allow all headers
)

# Allowed MIME types
ALLOWED_MIME_TYPES = [
    "application/pdf",  # PDF
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"  # .docx
]

# AWS S3 Configuration
AWS_ACCESS_KEY = settings.aws_access_key
AWS_SECRET_KEY = settings.aws_secret_key
BUCKET_NAME = settings.bucket_name

# S3 Client
s3_client = boto3.client(
    "s3",
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET_KEY
)

@app.post('/api/upload')
async def upload_pdf(company_name: str = Form(...), file: UploadFile = Form(...)):
    try:
        logger.info(f"Uploading {file.filename} for {company_name}")
        
        # Validate file type
        if file.content_type not in ALLOWED_MIME_TYPES:
            return JSONResponse(
                status_code=400,
                content={"message": "Invalid file type. Only PDF and DOCX files are allowed."}
            )

        # Define the S3 file key
        s3_file_key = f"{company_name}/{file.filename}"

        # Check if the file already exists in S3
        try:
            s3_client.head_object(Bucket=BUCKET_NAME, Key=s3_file_key)
            # If file exists, return its URL
            file_url = f"https://{BUCKET_NAME}.s3.amazonaws.com/{s3_file_key}"
            return JSONResponse(
                status_code=409,
                content={
                    "message": "File already exists in the S3 bucket.",
                    "file_url": file_url
                }
            )
        except s3_client.exceptions.ClientError as e:
            if e.response['Error']['Code'] != '404':
                logger.error(f"Failed to check if file exists: {str(e)}")
                return JSONResponse(
                    status_code=500,
                    content={"message": "Failed to check if file exists in S3."}
                )
            # File doesn't exist; continue to upload

        # Upload the file to S3
        s3_client.upload_fileobj(
            file.file,
            BUCKET_NAME,
            s3_file_key,
            ExtraArgs={"ContentType": file.content_type}
        )

        # Return success response with S3 file path
        file_url = f"https://{BUCKET_NAME}.s3.amazonaws.com/{s3_file_key}"
        return JSONResponse(
            status_code=200,
            content={
                "message": "File uploaded successfully",
                "file_url": file_url
            }
        )
    except NoCredentialsError:
        return JSONResponse(
            status_code=500,
            content={"message": "AWS credentials not available"}
        )
    except Exception as e:
        logger.error(f"Failed to upload {file.filename}: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"message": str(e)}
        )
    

# Run the app
# To run: uvicorn filename:app --reload
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)