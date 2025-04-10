# -*- coding: utf-8 -*-
"""ML_Project.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1PDpShZnOOjL-jc9fMZuq9D08COw5kCq0
"""

import pandas as pd
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, Dataset
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from tensorflow.keras.preprocessing.text import Tokenizer
from tensorflow.keras.preprocessing.sequence import pad_sequences
from imblearn.over_sampling import SMOTE
import pickle




dataset1_path = "/content/bot_detection_data.csv"
dataset2_path = "/content/training_data_2_csv_UTF (1).csv"


df1 = pd.read_csv(dataset1_path)
df2 = pd.read_csv(dataset2_path)
df = pd.concat([df1, df2], ignore_index=True)




df['Verified'] = pd.to_numeric(df['Verified'], errors='coerce').fillna(0).astype(int)
df.fillna("", inplace=True)
for feature in ['Retweet Count', 'Mention Count', 'Follower Count']:
    df[feature] = pd.to_numeric(df[feature], errors='coerce').fillna(0).astype(int)
df['Bot Label'] = pd.to_numeric(df['Bot Label'], errors='coerce').fillna(0).astype(int)


numerical_features = ['Retweet Count', 'Mention Count', 'Follower Count', 'Verified']
text_features = ['Username', 'Tweet']
target = 'Bot Label'




X_train_num, X_test_num, y_train, y_test = train_test_split(df[numerical_features], df[target], test_size=0.2, random_state=42)
y_train = y_train.astype(int)


smote = SMOTE()
X_train_num, y_train = smote.fit_resample(X_train_num, y_train)




scaler = StandardScaler()
X_train_num = scaler.fit_transform(X_train_num)
X_test_num = scaler.transform(X_test_num)




tokenizer = Tokenizer(num_words=5000)
tokenizer.fit_on_texts(df["Tweet"].tolist() + df["Username"].tolist())


X_train_text = tokenizer.texts_to_sequences(df.loc[y_train.index, text_features].agg(' '.join, axis=1))
X_test_text = tokenizer.texts_to_sequences(df.loc[y_test.index, text_features].agg(' '.join, axis=1))


X_train_text = pad_sequences(X_train_text, maxlen=50)
X_test_text = pad_sequences(X_test_text, maxlen=50)




X_train_text = torch.tensor(X_train_text, dtype=torch.long)
X_test_text = torch.tensor(X_test_text, dtype=torch.long)
X_train_num = torch.tensor(X_train_num, dtype=torch.float32)
X_test_num = torch.tensor(X_test_num, dtype=torch.float32)
y_train = torch.tensor(y_train.values, dtype=torch.long)
y_test = torch.tensor(y_test.values, dtype=torch.long)




class BotDataset(Dataset):
    def __init__(self, text_data, num_data, labels):
        self.text_data = text_data
        self.num_data = num_data
        self.labels = labels


    def __len__(self):
        return len(self.labels)


    def __getitem__(self, idx):
        return self.text_data[idx], self.num_data[idx], self.labels[idx]


train_dataset = BotDataset(X_train_text, X_train_num, y_train)
test_dataset = BotDataset(X_test_text, X_test_num, y_test)


train_loader = DataLoader(train_dataset, batch_size=32, shuffle=True)
test_loader = DataLoader(test_dataset, batch_size=32)


# CNN + LSTM Model
class BotCNNLSTM(nn.Module):
    def __init__(self, vocab_size, embedding_dim, num_filters, kernel_size, hidden_dim, num_classes):
        super(BotCNNLSTM, self).__init__()
        self.embedding = nn.Embedding(vocab_size, embedding_dim)
        self.conv1 = nn.Conv1d(in_channels=embedding_dim, out_channels=num_filters, kernel_size=kernel_size)
        self.lstm = nn.LSTM(num_filters, hidden_dim, batch_first=True)
        self.fc1 = nn.Linear(hidden_dim, 64)
        self.fc2 = nn.Linear(64 + len(numerical_features), num_classes)


    def forward(self, text_input, num_input):
        x = self.embedding(text_input).permute(0, 2, 1)
        x = torch.relu(self.conv1(x))
        x = x.permute(0, 2, 1)
        x, _ = self.lstm(x)
        x = self.fc1(x[:, -1, :])
        x = torch.cat((x, num_input), dim=1)
        x = self.fc2(x)
        return x




device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model = BotCNNLSTM(vocab_size=5000, embedding_dim=128, num_filters=64, kernel_size=3, hidden_dim=64, num_classes=4).to(device)
criterion = nn.CrossEntropyLoss()
optimizer = optim.Adam(model.parameters(), lr=1e-3)


for epoch in range(3):
    model.train()
    total_loss = 0
    for text_batch, num_batch, labels in train_loader:
        text_batch, num_batch, labels = text_batch.to(device), num_batch.to(device), labels.to(device)
        optimizer.zero_grad()
        outputs = model(text_batch, num_batch)
        loss = criterion(outputs, labels)
        loss.backward()
        optimizer.step()
        total_loss += loss.item()
    print(f"Epoch {epoch+1}/3, Loss: {total_loss/len(train_loader):.4f}")




torch.save(model.state_dict(), "cnn_lstm_bot_model.pth")
with open("tokenizer.pkl", "wb") as f:
    pickle.dump(tokenizer, f)
with open("scaler.pkl", "wb") as f:
    pickle.dump(scaler, f)




def predict_bot(username, tweet, retweet_count, mention_count, follower_count, verified):
    user_input_df = pd.DataFrame([[retweet_count, mention_count, follower_count, verified]],
                                 columns=numerical_features)
    scaled_input = scaler.transform(user_input_df)
    user_text = tokenizer.texts_to_sequences([username + " " + tweet])
    user_text = pad_sequences(user_text, maxlen=50)
    X_test_text = torch.tensor(user_text, dtype=torch.long).to(device)
    X_test_num = torch.tensor(scaled_input, dtype=torch.float32).to(device)
    model.eval()
    with torch.no_grad():
        output = model(X_test_text, X_test_num)
        prediction = torch.argmax(output, dim=1).item()
    class_labels = ["Human", "Spam Bot", "Chatbot", "News Bot"]
    return class_labels[prediction]




username = input("Enter Username: ")
tweet = input("Enter Tweet: ")
retweet_count = int(input("Enter Retweet Count: "))
mention_count = int(input("Enter Mention Count: "))
follower_count = int(input("Enter Follower Count: "))
verified = 1 if input("Is the user verified? (True/False): ").strip().lower() == "true" else 0


result = predict_bot(username, tweet, retweet_count, mention_count, follower_count, verified)
print("Prediction:", result)