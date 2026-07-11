// Source: data/benchmarks/LinearArbitrary-SeaHorn/pie/hola/13.c

extern int unknown1();
extern int unknown2();
extern int unknown3();
extern int unknown4();

void loopy_125(int flag) {
   int j = 2; 
   int k = 0;

   

   while(unknown1()){ 
     if (flag)
       j = j + 4;
     else {
       j = j + 2;
       k = k + 1;
     }
   }
   if(k!=0)
     {;
//@ assert(j==2*k+2);
}

   return;
}