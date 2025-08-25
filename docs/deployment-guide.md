# RAG Chatbot Deployment Guide for Non-Developers

This guide will walk you through deploying your RAG Chatbot step-by-step, even if you have no technical background.

## 📋 What You'll Need

Before starting, make sure you have:

1. **A computer** (Windows, Mac, or Linux)
2. **An AWS account** (we'll help you set this up)
3. **About 15 minutes** of your time
4. **Your business documents** (PDFs, Word docs, etc.) that you want the chatbot to learn from


## 🚀 Step-by-Step Deployment

### Step 1: Set Up Your AWS Account

1. **Create an AWS Account**:
   - Go to [aws.amazon.com](https://aws.amazon.com)
   - Click "Create an AWS Account"
   - Follow the signup process (you'll need a credit card)

2. **Set Up AWS CLI** (this lets your computer talk to AWS):
   
   **For Windows:**
   ```cmd
   # Download and install from: https://aws.amazon.com/cli/
   # After installation, open Command Prompt and run:
   aws configure
   ```
   
   **For Mac:**
   ```bash
   # Install using Homebrew (if you don't have it, get it from brew.sh)
   brew install awscli
   aws configure
   ```
   
   **For Linux:**
   ```bash
   sudo apt install awscli  # Ubuntu/Debian
   # or
   sudo yum install awscli  # CentOS/RHEL
   aws configure
   ```

3. **Configure AWS CLI**:
   When you run `aws configure`, you'll be asked for:
   - **Access Key ID**: Get this from AWS Console → IAM → Users → Your User → Security Credentials
   - **Secret Access Key**: You'll get this with the Access Key
   - **Region**: Choose the region closest to you (e.g., `us-east-1` for US East Coast)
   - **Output format**: Just press Enter (uses default)

### Step 2: Deploy Your Chatbot

#### Option A: Super Easy One-Line Install (Recommended)

1. **Open Terminal/Command Prompt**:
   - **Windows**: Press `Win + R`, type `cmd`, press Enter
   - **Mac**: Press `Cmd + Space`, type "Terminal", press Enter
   - **Linux**: Press `Ctrl + Alt + T`

2. **Run the installer**:
   ```bash
   curl -sSL https://raw.githubusercontent.com/your-github-username/aws-bedrock-chatbot-solution/main/install.sh | bash
   ```

   **Replace `your-github-username` with your actual GitHub username**

3. **Wait for deployment** (15 minutes):
   The installer handles everything automatically!

#### Option B: Manual Deployment

1. **Download the code**:
   ```bash
   git clone https://github.com/your-github-username/aws-bedrock-chatbot-solution.git
   cd aws-bedrock-chatbot-solution
   ```

   **Replace `your-github-username` with your actual GitHub username**

2. **Run deployment**:
   ```bash
   ./deploy.sh
   ```

3. **Follow the prompts**:
   - Choose your AWS region
   - Select your brand colors

### Step 3: Add Your Knowledge Base

After deployment completes:

```bash
# 1. Create documents folder
mkdir documents

# 2. Add your business documents
# Copy your PDF, Word, text files to the documents folder

# 3. Upload to your chatbot
python3 -m scripts.upload_documents --folder ./documents
```

### Step 4: Add to Your Website

Copy the provided integration code to your website, for example:

```html
<script src="https://your-domain.cloudfront.net/widget.js"></script>
<script>
  SmallBizChatbot.init({
    containerId: 'chatbot-container'
  });
</script>
<div id="chatbot-container"></div>
```

**How to add it to your website:**

1. **WordPress**: Add to a Custom HTML block or in Appearance → Theme Editor
2. **Squarespace**: Add to a Code Block
3. **Wix**: Add to an HTML Component
4. **Shopify**: Add to your theme's template files
5. **Custom website**: Add to your HTML file where you want the chatbot to appear

## 🆘 Troubleshooting

### If Deployment Fails

1. **Try recovery**: `./deploy.sh --recover`
2. **Check the log**: `cat deployment.log`
3. **Start fresh**: `./deploy.sh rollback` then `./deploy.sh`

### Common Issues

**"AWS credentials not configured"**
- Solution: Run `aws configure` and enter your Access Key and Secret Key

**"Python version too old"**
- Solution: Install Python 3.12+ from python.org

**"Permission denied"**
- Solution: Ask your AWS admin for AdministratorAccess policy

**"Network error"**
- Solution: Check your internet connection and try again

### Get Help

- 📖 [Troubleshooting Guide](troubleshooting.md)
- 🐛 [Report Issues](https://github.com/your-github-username/aws-bedrock-chatbot-solution/issues)
- 💬 [Community Forum](https://github.com/your-github-username/aws-bedrock-chatbot-solution/discussions)

**Replace `your-github-username` with your actual GitHub username in the URLs above.**

## 🔧 Managing Your Chatbot

### Adding More Documents
```bash
# Add new files to the documents folder, then run:
python3 -m scripts.upload_documents --folder ./documents
```

### Updating Your Chatbot
```bash
# If you make changes to configuration:
./deploy.sh
```

### Viewing Usage and Costs
1. Go to [AWS Console](https://console.aws.amazon.com)
2. Navigate to CloudWatch → Dashboards
3. Look for "ChatbotRag" dashboard

## ✅ Success!

Once deployment completes, you'll have:
- ✅ A live AI chatbot
- ✅ Secure AWS infrastructure
- ✅ Embeddable widget for your website
- ✅ Knowledge base from your documents
- ✅ Real-time streaming responses
- ✅ Built-in security and monitoring

## 📈 What's Next?

1. **Test your chatbot** on the demo page
2. **Add more documents** to improve responses
3. **Customize the appearance** to match your brand
4. **Monitor usage** in AWS CloudWatch
5. **Scale up** as your business grows

Your AI assistant is now ready to help your customers 24/7!
