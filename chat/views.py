import re
import requests
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.conf import settings
from .models import ChatThread, Message
from .forms import SignUpForm, LoginForm, MessageForm


def clean_safety_output(text):
    if not text:
        return ""
    lines = text.splitlines()
    cleaned_lines = []
    for line in lines:
        stripped = line.strip()
        if re.match(r'^(User Safety|Response Safety|Prompt Safety|Safety Rating|Safety Evaluation|Safety)\s*:\s*(safe|unsafe|neutral|none|low|medium|high|harmful|\w+)\s*$', stripped, re.IGNORECASE):
            continue
        cleaned_lines.append(line)
    return "\n".join(cleaned_lines).strip()


def signup_view(request):
    if request.user.is_authenticated:
        return redirect('thread_list')
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('thread_list')
    else:
        form = SignUpForm()
    return render(request, 'chat/signup.html', {'form': form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect('thread_list')
    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        # If input looks like an email, find the matching username
        identifier = request.POST.get('username', '').strip()
        if '@' in identifier:
            try:
                user_obj = User.objects.get(email=identifier)
                # Replace the POST data username with the actual username
                data = request.POST.copy()
                data['username'] = user_obj.username
                form = LoginForm(request, data=data)
            except User.DoesNotExist:
                pass  # Let form handle the invalid login error
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('thread_list')
    else:
        form = LoginForm(request)
    return render(request, 'chat/login.html', {'form': form})


@login_required
def thread_list_view(request):
    if request.method == 'POST':
        thread = ChatThread.objects.create(user=request.user, title='New Chat')
        return redirect('thread_detail', thread_id=thread.id)
    threads = ChatThread.objects.filter(user=request.user)
    return render(request, 'chat/thread_list.html', {'threads': threads})


@login_required
def thread_detail_view(request, thread_id):
    thread = get_object_or_404(ChatThread, id=thread_id, user=request.user)
    threads = ChatThread.objects.filter(user=request.user)

    if request.method == 'POST':
        is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'application/json' in request.headers.get('Accept', '')
        form = MessageForm(request.POST)
        if form.is_valid():
            user_text = form.cleaned_data['content']
            Message.objects.create(thread=thread, role='user', content=user_text)

            if thread.title == 'New Chat':
                thread.title = user_text[:30]
                thread.save()

            api_key = settings.OPENROUTER_API_KEY
            model = settings.OPENROUTER_MODEL

            headers = {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
                'HTTP-Referer': 'https://task1.vercel.app',
                'X-Title': 'Task1 Chat App',
            }

            messages_payload = [
                {'role': m.role, 'content': m.content}
                for m in thread.messages.all()
            ]
            # Try preferred free models first, avoiding content-safety evaluator models
            preferred_model = model if (model and 'gemini-2.0-flash-exp' not in model and 'content-safety' not in model) else 'openrouter/free'
            models_to_try = list(dict.fromkeys([
                preferred_model,
                'google/gemma-4-31b-it:free',
                'google/gemma-4-26b-a4b-it:free',
                'openrouter/free',
                'liquid/lfm-2.5-2.6b:free',
                'poolside/laguna-s-2.1:free',
                'z-ai/glm-5.2:free',
            ]))

            bot_text = None
            last_error = "Unknown error"

            for candidate_model in models_to_try:
                try:
                    payload = {
                        'model': candidate_model,
                        'messages': messages_payload,
                    }
                    res = requests.post(
                        'https://openrouter.ai/api/v1/chat/completions',
                        json=payload,
                        headers=headers,
                        timeout=25,
                    )
                    if res.status_code == 200:
                        data = res.json()
                        raw_content = data['choices'][0]['message']['content']
                        cleaned_content = clean_safety_output(raw_content)
                        if cleaned_content:
                            bot_text = cleaned_content
                            break
                        else:
                            last_error = "Model returned only safety metadata."
                    else:
                        last_error = f"API Error ({res.status_code}): {res.text}"
                except Exception as e:
                    last_error = f"Error communicating with AI: {str(e)}"

            if bot_text is None:
                bot_text = last_error if "API Error" in last_error else "I was unable to generate a response. Please try again."

            Message.objects.create(thread=thread, role='assistant', content=bot_text)

            if is_ajax:
                return JsonResponse({
                    'status': 'ok',
                    'user_message': user_text,
                    'assistant_message': bot_text,
                    'thread_title': thread.title,
                })

            return redirect('thread_detail', thread_id=thread.id)
        else:
            if is_ajax:
                return JsonResponse({'status': 'error', 'error': 'Invalid message'}, status=400)
    else:
        form = MessageForm()

    return render(request, 'chat/thread_detail.html', {
        'thread': thread,
        'threads': threads,
        'chat_messages': thread.messages.all(),
        'form': form,
    })


@login_required
def thread_delete_view(request, thread_id):
    thread = get_object_or_404(ChatThread, id=thread_id, user=request.user)
    if request.method == 'POST':
        thread.delete()
    return redirect('thread_list')
