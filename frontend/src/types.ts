export interface Message {
  id: number;
  text: string;
  sender: 'user' | 'bot';
  time: string;
  audio?: string; // Base64 audio content
}

export interface Property {
  id: number;
  sequence: number;
  name: string;
  type: string;
  price: string;
  location: string;
  description: string;
  property_heading?: string;
  status: 'Available' | 'Sold' | 'Reserved';
}

export interface Lead {
  id: number;
  name: string;
  phone: string;
  status: 'New' | 'Connected' | 'Site Visit Booked' | 'No Answer';
  interest: string;
  date: string;
}

export interface CallLog {
  id: number;
  leadName: string;
  phone: string;
  date: string;
  duration: string;
  status: string;
  summary: string;
  toPhone?: string;
  direction?: string;
  flowName?: string;
  outcome?: string;
  callSid?: string;
  transcript?: string;
}
